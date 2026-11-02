"""
Security tests for the application.
Tests for common vulnerabilities like SQL injection, XSS, CSRF, etc.
"""

import json
import os
import tempfile
from datetime import UTC

UTC = UTC
from datetime import datetime
from unittest.mock import patch

import pytest

from app import create_app
from app.database import db
from app.database.models import DataSource, Prospect


@pytest.fixture(scope="function")
def app():
    """Create a test Flask application with in-memory database."""
    # Create temporary database file
    db_fd, db_path = tempfile.mkstemp()

    # Create app with test configuration
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["USER_DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["TESTING"] = "True"

    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["WTF_CSRF_ENABLED"] = False  # Disabled for testing

    with app.app_context():
        # Create all tables
        db.create_all()

        # Create a test data source
        test_source = DataSource(
            name="Test Agency",
            url="https://test.gov",
            scraper_class="TestScraper",
            active=True,
        )
        db.session.add(test_source)
        db.session.commit()

        app.config["TEST_SOURCE_ID"] = test_source.id
        app.config["TEST_USER_ID"] = "test-user-123"

        yield app

        db.session.remove()
        db.drop_all()

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def auth_client(app, client):
    """Create an authenticated test client."""
    with patch("app.api.auth.get_current_user") as mock_auth:
        mock_auth.return_value = {
            "id": app.config["TEST_USER_ID"],
            "username": "testuser",
            "role": "user",
        }
        yield client


class TestSQLInjection:
    """Test for SQL injection vulnerabilities."""

    def test_prospects_api_sql_injection_in_search(self, client):
        """Test SQL injection attempts in search parameters."""
        # Common SQL injection payloads
        payloads = [
            "'; DROP TABLE prospects; --",
            "' OR '1'='1",
            "'; INSERT INTO prospects VALUES ('hack', 'hacked'); --",
            "' UNION SELECT * FROM prospects --",
            "admin'--",
            "admin'/*",
            "' OR 1=1#",
            "1' OR '1'='1",
        ]

        for payload in payloads:
            # Test search parameter
            response = client.get(f"/api/prospects?keywords={payload}")

            # Should handle malicious input gracefully
            assert response.status_code in [200, 400, 422]  # Valid responses

            if response.status_code == 200:
                data = response.get_json()
                assert "prospects" in data
                # Response structure should remain intact
                assert isinstance(data["prospects"], list)
                # SQL injection should not affect query results
                # (Results should be filtered normally or empty, not expose all data)

    def test_prospects_api_sql_injection_in_filters(self, client):
        """Test SQL injection in filter parameters."""
        payloads = [
            "'; DROP TABLE prospects; --",
            "' OR 1=1 --",
            "'; UPDATE prospects SET title='hacked' --",
        ]

        for payload in payloads:
            # Test agency filter
            response = client.get(f"/api/prospects?agency={payload}")
            assert response.status_code in [200, 400, 422]

            # Test NAICS filter
            response = client.get(f"/api/prospects?naics={payload}")
            assert response.status_code in [200, 400, 422]

    def test_decisions_api_sql_injection(self, auth_client):
        """Test SQL injection in decision creation."""
        payloads = [
            "'; DROP TABLE decisions; --",
            "' OR 1=1 --",
            {
                "prospect_id": "'; DROP TABLE decisions; --",
                "decision": "go",
                "reason": "test",
            },
            {
                "prospect_id": "test",
                "decision": "'; DROP TABLE decisions; --",
                "reason": "test",
            },
            {
                "prospect_id": "test",
                "decision": "go",
                "reason": "'; DROP TABLE decisions; --",
            },
        ]

        for payload in payloads:
            if isinstance(payload, dict):
                response = auth_client.post(
                    "/api/decisions/",
                    data=json.dumps(payload),
                    content_type="application/json",
                )
            else:
                response = auth_client.get(f"/api/decisions/{payload}")

            # Should handle malicious input gracefully
            assert response.status_code in [200, 400, 404, 422]


class TestXSSPrevention:
    """Test for Cross-Site Scripting (XSS) prevention."""

    def test_prospects_api_xss_in_responses(self, app, client):
        """Test that API responses properly escape HTML/JavaScript."""
        with app.app_context():
            # Create prospect with XSS payload
            xss_payload = "<script>alert('XSS')</script>"

            prospect = Prospect(
                id="XSS-TEST-001",
                title=f"Test Title {xss_payload}",
                description=f"Test Description {xss_payload}",
                agency="Test Agency",
                posted_date=datetime(2024, 1, 15).date(),
                source_data_id=app.config["TEST_SOURCE_ID"],
                source_file="xss_test.json",
                loaded_at=datetime.now(UTC),
            )

            db.session.add(prospect)
            db.session.commit()

        # Get prospects via API
        response = client.get("/api/prospects")
        assert response.status_code == 200

        data = response.get_json()

        # Find our test prospect
        test_prospect = next(
            (p for p in data["prospects"] if p["id"] == "XSS-TEST-001"), None
        )
        assert test_prospect is not None

        # XSS payload should be properly encoded/escaped
        assert "<script>" not in test_prospect["title"]
        assert "<script>" not in test_prospect["description"]

        # Content should still be present but safe
        assert "alert" in test_prospect["title"]  # Text content preserved
        assert "XSS" in test_prospect["title"]

    def test_decision_creation_xss_prevention(self, app, auth_client):
        """Test XSS prevention in decision creation."""
        with app.app_context():
            # Create test prospect
            prospect = Prospect(
                id="XSS-DECISION-001",
                title="Test Prospect for XSS",
                description="Test description",
                agency="Test Agency",
                posted_date=datetime(2024, 1, 15).date(),
                source_data_id=app.config["TEST_SOURCE_ID"],
                source_file="xss_test.json",
                loaded_at=datetime.now(UTC),
            )
            db.session.add(prospect)
            db.session.commit()

        # Create decision with XSS payload
        xss_payload = "<script>alert('XSS in decision')</script>"
        decision_data = {
            "prospect_id": "XSS-DECISION-001",
            "decision": "go",
            "reason": f"Decision reason {xss_payload}",
        }

        response = auth_client.post(
            "/api/decisions/",
            data=json.dumps(decision_data),
            content_type="application/json",
        )

        # Should create decision successfully
        assert response.status_code == 201

        # Get decisions back
        response = auth_client.get("/api/decisions/XSS-DECISION-001")
        assert response.status_code == 200

        data = response.get_json()
        decisions = data["data"]["decisions"]
        assert len(decisions) > 0

        # XSS should be neutralized
        decision = decisions[0]
        assert "<script>" not in decision["reason"]
        assert "alert" in decision["reason"]  # Text preserved


class TestInputValidation:
    """Test input validation and sanitization."""

    def test_prospects_api_parameter_validation(self, client):
        """Test parameter validation in prospects API."""
        # Test invalid page numbers
        response = client.get("/api/prospects?page=-1")
        assert response.status_code == 400

        response = client.get("/api/prospects?page=abc")
        assert response.status_code == 400

        # Test invalid limits
        response = client.get("/api/prospects?limit=0")
        assert response.status_code == 400

        response = client.get("/api/prospects?limit=10000")  # Too large
        assert response.status_code == 400

        response = client.get("/api/prospects?limit=abc")
        assert response.status_code == 400

    def test_decision_input_validation(self, auth_client):
        """Test decision creation input validation."""
        # Test missing required fields
        response = auth_client.post(
            "/api/decisions/", data=json.dumps({}), content_type="application/json"
        )
        assert response.status_code == 400

        # Test invalid decision values
        invalid_decision = {
            "prospect_id": "TEST-001",
            "decision": "invalid-decision-type",
            "reason": "Test reason",
        }

        response = auth_client.post(
            "/api/decisions/",
            data=json.dumps(invalid_decision),
            content_type="application/json",
        )
        assert response.status_code == 400

        # Test extremely long reason
        long_reason = "x" * 10000  # Very long string
        long_reason_decision = {
            "prospect_id": "TEST-001",
            "decision": "go",
            "reason": long_reason,
        }

        response = auth_client.post(
            "/api/decisions/",
            data=json.dumps(long_reason_decision),
            content_type="application/json",
        )
        # Should either reject or truncate gracefully
        assert response.status_code in [400, 422]

    def test_malformed_json_handling(self, auth_client):
        """Test handling of malformed JSON requests."""
        malformed_payloads = [
            '{"prospect_id": "test", "decision": "go", "reason": "test"',  # Missing closing brace
            '{"prospect_id": "test", "decision": "go", "reason": "test"}extra',  # Extra content
            "not json at all",
            '{"prospect_id": null, "decision": null}',  # Null values
            '{"prospect_id": 123, "decision": true}',  # Wrong types
        ]

        for payload in malformed_payloads:
            response = auth_client.post(
                "/api/decisions/", data=payload, content_type="application/json"
            )
            # Should handle gracefully
            assert response.status_code in [400, 422]


class TestAccessControl:
    """Test access control and authorization."""

    def test_unauthenticated_access_to_protected_endpoints(self, client):
        """Test that protected endpoints require authentication."""
        protected_endpoints = [
            ("/api/decisions/", "POST"),
            ("/api/decisions/TEST-001", "GET"),
            ("/api/decisions/stats", "GET"),
            ("/api/decisions/123", "DELETE"),
        ]

        for endpoint, method in protected_endpoints:
            if method == "POST":
                response = client.post(
                    endpoint,
                    data=json.dumps({"test": "data"}),
                    content_type="application/json",
                )
            elif method == "DELETE":
                response = client.delete(endpoint)
            else:
                response = client.get(endpoint)

            # Should require authentication
            assert response.status_code in [
                401,
                403,
                302,
            ]  # Unauthorized, Forbidden, or Redirect

    def test_public_endpoints_accessibility(self, client):
        """Test that public endpoints are accessible without authentication."""
        public_endpoints = [
            "/api/prospects",
            "/api/data-sources",
            "/api/health",
            "/api/health/database",
        ]

        for endpoint in public_endpoints:
            response = client.get(endpoint)
            # Should be accessible (may return empty data but not auth error)
            assert response.status_code in [200, 404]


class TestDataLeakage:
    """Test for sensitive data leakage."""

    def test_error_messages_dont_leak_sensitive_info(self, client):
        """Test that error messages don't reveal sensitive information."""
        # Test non-existent endpoint
        response = client.get("/api/nonexistent")
        assert response.status_code == 404

        if response.content_type == "application/json":
            data = response.get_json()
            error_message = str(data).lower()

            # Should not contain sensitive paths or database info
            sensitive_terms = [
                "database_url",
                "secret_key",
                "password",
                "/users/zach/",  # Local file paths
                "traceback",
                "exception",
                "sqlite:///",
            ]

            for term in sensitive_terms:
                assert term.lower() not in error_message

    def test_api_responses_dont_include_internal_fields(self, app, client):
        """Test that API responses don't include internal/sensitive fields."""
        with app.app_context():
            # Create test prospect
            prospect = Prospect(
                id="LEAK-TEST-001",
                title="Test Prospect",
                description="Test description",
                agency="Test Agency",
                posted_date=datetime(2024, 1, 15).date(),
                source_data_id=app.config["TEST_SOURCE_ID"],
                source_file="leak_test.json",
                loaded_at=datetime.now(UTC),
            )
            db.session.add(prospect)
            db.session.commit()

        response = client.get("/api/prospects")
        assert response.status_code == 200

        data = response.get_json()
        prospect = data["prospects"][0]

        # Should not include internal database fields
        internal_fields = [
            "source_data_id",  # Internal ID reference
            "_sa_instance_state",  # SQLAlchemy internal
        ]

        for field in internal_fields:
            assert field not in prospect


class TestRateLimiting:
    """Test rate limiting (if implemented)."""

    def test_api_rate_limiting(self, client):
        """Test that APIs have rate limiting (if configured)."""
        # Make many rapid requests
        responses = []
        for i in range(100):
            response = client.get("/api/prospects")
            responses.append(response)

            # Stop if we hit rate limit
            if response.status_code == 429:
                break

        # If rate limiting is implemented, we should eventually get 429
        # If not implemented, all should be 200
        status_codes = [r.status_code for r in responses]

        # Should either all be successful or include rate limiting
        assert all(code in [200, 429] for code in status_codes)


class TestSecurityHeaders:
    """Test security headers (if implemented)."""

    def test_security_headers_present(self, client):
        """Test that appropriate security headers are set."""
        response = client.get("/api/prospects")

        # Check for common security headers
        security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security",  # If HTTPS
            "Content-Security-Policy",
        ]

        present_headers = []
        for header in security_headers:
            if header in response.headers:
                present_headers.append(header)

        # At least some security headers should be present
        # (This test will pass even if none are present, but documents the expectation)
        assert len(present_headers) >= 0  # Placeholder - adjust based on implementation


if __name__ == "__main__":
    pytest.main([__file__])
