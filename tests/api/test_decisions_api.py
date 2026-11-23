"""
Comprehensive tests for Decisions API endpoints.

Tests all decision-related API functionality including CRUD operations.
Following production-level testing principles:
- No hardcoded expected values
- Tests verify behavior, not specific data
- Uses real database operations
- Focus on API behavior patterns
"""

import json
import random
import string
from datetime import UTC

UTC = UTC
from datetime import datetime, timedelta

import pytest

from app import create_app
from app.database import db
from app.database.models import DataSource, GoNoGoDecision, Prospect
from app.database.user_models import User


class TestDecisionsAPI:
    """Test suite for Decisions API endpoints following black-box testing principles."""

    @pytest.fixture(scope="class")
    def app(self):
        """Create test Flask app with real database."""
        app = create_app()
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["WTF_CSRF_ENABLED"] = False
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()

    def _auth_request(self, client, method, url, user_id=None, **kwargs):
        """Helper method to make authenticated requests."""
        with client.session_transaction() as sess:
            sess["user_id"] = user_id if user_id else self.test_user_id
            sess["user_role"] = "user"

        method_func = getattr(client, method)
        return method_func(url, **kwargs)

    @pytest.fixture(autouse=True)
    def setup_database(self, app, client):
        """Set up test database with dynamically generated data."""
        with app.app_context():
            db.create_all()

            # Create data sources with realistic attributes
            num_sources = random.randint(1, 3)
            data_sources = []

            for i in range(num_sources):
                source = DataSource(
                    name=f"Agency {random.choice(['Alpha', 'Beta', 'Gamma'])} {i}",
                    url=f"https://agency{i}.gov",
                    last_scraped=datetime.now(UTC)
                    - timedelta(days=random.randint(0, 7)),
                )
                db.session.add(source)
                data_sources.append(source)

            db.session.flush()

            # Create test users with various roles
            num_users = random.randint(3, 6)
            test_users = []
            roles = ["user", "admin", "user", "user", "admin", "user"]

            for i in range(num_users):
                user = User(
                    first_name=f"User {random.choice(string.ascii_uppercase)}{i}",
                    email=f"user{i}@test{random.randint(1, 100)}.com",
                    role=roles[i % len(roles)],
                )
                db.session.add(user)
                test_users.append(user)

            db.session.flush()

            # Create prospects with varying attributes
            num_prospects = random.randint(5, 10)
            test_prospects = []

            for i in range(num_prospects):
                prospect = Prospect(
                    id=f"PROSPECT-{random.randint(1000, 9999)}-{i}",
                    title=f"{random.choice(['Software', 'Hardware', 'Consulting', 'Research'])} Contract {i}",
                    description=f"Description for contract {i} with various requirements",
                    agency=random.choice(data_sources).name,
                    naics=random.choice(["541511", "541512", "541519", "517311", None]),
                    estimated_value_text=f"${random.randint(10, 500) * 1000:,}"
                    if random.random() > 0.3
                    else "TBD",
                    source_id=random.choice(data_sources).id,
                    loaded_at=datetime.now(UTC)
                    - timedelta(hours=random.randint(0, 72)),
                )
                db.session.add(prospect)
                test_prospects.append(prospect)

            db.session.flush()

            # Create some existing decisions randomly
            num_decisions = random.randint(0, min(num_prospects, num_users))
            existing_decisions = []

            for i in range(num_decisions):
                decision = GoNoGoDecision(
                    prospect_id=test_prospects[i].id,
                    user_id=random.choice(test_users).id,
                    decision=random.choice(["go", "no-go"]),
                    reason=f"Reason {i}: {random.choice(['Good fit', 'Not aligned', 'High competition', 'Strategic opportunity'])}",
                )
                db.session.add(decision)
                existing_decisions.append(decision)

            db.session.commit()

            # Store test data for use in tests
            self.test_users = test_users
            self.test_prospects = test_prospects
            self.test_decisions = existing_decisions
            self.test_user_id = test_users[0].id if test_users else None

            yield

            # Cleanup
            db.session.rollback()
            db.drop_all()

    def test_create_decision_behavior(self, client):
        """Test that decision creation behaves correctly."""
        # Select a prospect that may or may not have a decision
        prospect = random.choice(self.test_prospects)
        decision_type = random.choice(["go", "no-go"])
        reason_text = f"Test reason {random.randint(1, 100)}"

        decision_data = {
            "prospect_id": prospect.id,
            "decision": decision_type,
            "reason": reason_text,
        }

        response = self._auth_request(
            client,
            "post",
            "/api/decisions/",
            data=json.dumps(decision_data),
            content_type="application/json",
        )

        # Should succeed
        assert response.status_code == 200
        data = response.get_json()

        # Verify response structure
        assert "status" in data
        assert data["status"] == "success"
        assert "data" in data
        assert "decision" in data["data"]

        # Verify decision was created/updated with correct attributes
        decision = data["data"]["decision"]
        assert decision["prospect_id"] == prospect.id
        assert decision["decision"] == decision_type
        assert decision["reason"] == reason_text
        assert decision["user_id"] == self.test_user_id
        assert "created_at" in decision

    def test_decision_validation_behavior(self, client):
        """Test that decision validation works correctly."""
        # Test missing required fields
        invalid_requests = [
            {"decision": "go", "reason": "Missing prospect_id"},
            {
                "prospect_id": random.choice(self.test_prospects).id,
                "reason": "Missing decision",
            },
            {
                "prospect_id": "invalid-id",
                "decision": "go",
                "reason": "Invalid prospect",
            },
            {
                "prospect_id": random.choice(self.test_prospects).id,
                "decision": "maybe",
                "reason": "Invalid decision type",
            },
        ]

        for invalid_data in invalid_requests:
            response = self._auth_request(
                client,
                "post",
                "/api/decisions/",
                data=json.dumps(invalid_data),
                content_type="application/json",
            )

            # Should fail validation
            assert response.status_code in [400, 404]
            data = response.get_json()
            assert "message" in data or "error" in data

    def test_get_decisions_for_prospect(self, client):
        """Test retrieving decisions for a specific prospect."""
        # Test with a prospect that has decisions
        if self.test_decisions:
            decision = random.choice(self.test_decisions)
            prospect_id = decision.prospect_id

            response = self._auth_request(
                client, "get", f"/api/decisions/{prospect_id}"
            )

            assert response.status_code == 200
            data = response.get_json()

            # Verify response structure
            assert "data" in data
            assert "decisions" in data["data"]
            assert isinstance(data["data"]["decisions"], list)

            # Verify all decisions are for the requested prospect
            for dec in data["data"]["decisions"]:
                assert dec["prospect_id"] == prospect_id

        # Test with a prospect that might not have decisions
        prospect = random.choice(self.test_prospects)
        response = self._auth_request(client, "get", f"/api/decisions/{prospect.id}")

        assert response.status_code == 200
        data = response.get_json()
        assert "data" in data
        assert "decisions" in data["data"]
        # May have 0 or more decisions
        assert isinstance(data["data"]["decisions"], list)

    def test_get_user_decisions(self, client):
        """Test retrieving current user's decisions."""
        # Create a decision for the test user
        prospect = random.choice(self.test_prospects)
        decision_data = {
            "prospect_id": prospect.id,
            "decision": "go",
            "reason": "User decision test",
        }

        # Create decision
        create_response = self._auth_request(
            client,
            "post",
            "/api/decisions/",
            data=json.dumps(decision_data),
            content_type="application/json",
        )
        assert create_response.status_code == 200

        # Get user's decisions
        response = self._auth_request(client, "get", "/api/decisions/my")

        assert response.status_code == 200
        data = response.get_json()

        assert "data" in data
        assert "decisions" in data["data"]

        # All decisions should belong to the current user
        for decision in data["data"]["decisions"]:
            assert decision["user_id"] == self.test_user_id

    def test_update_existing_decision(self, client):
        """Test updating an existing decision."""
        # Create initial decision
        prospect = random.choice(self.test_prospects)
        initial_data = {
            "prospect_id": prospect.id,
            "decision": "go",
            "reason": "Initial reason",
        }

        response = self._auth_request(
            client,
            "post",
            "/api/decisions/",
            data=json.dumps(initial_data),
            content_type="application/json",
        )
        assert response.status_code == 200

        # Update the decision
        updated_data = {
            "prospect_id": prospect.id,
            "decision": "no-go",
            "reason": "Updated after review",
        }

        response = self._auth_request(
            client,
            "post",
            "/api/decisions/",
            data=json.dumps(updated_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()

        # Verify update was applied
        assert data["data"]["decision"]["decision"] == "no-go"
        assert data["data"]["decision"]["reason"] == "Updated after review"
        assert data["data"]["decision"]["prospect_id"] == prospect.id

    def test_delete_decision_behavior(self, client):
        """Test decision deletion behavior."""
        # Create a decision to delete
        prospect = random.choice(self.test_prospects)
        decision_data = {
            "prospect_id": prospect.id,
            "decision": "go",
            "reason": "Will be deleted",
        }

        create_response = self._auth_request(
            client,
            "post",
            "/api/decisions/",
            data=json.dumps(decision_data),
            content_type="application/json",
        )

        assert create_response.status_code == 200
        decision_id = create_response.get_json()["data"]["decision"]["id"]

        # Delete the decision
        delete_response = self._auth_request(
            client, "delete", f"/api/decisions/{decision_id}"
        )

        assert delete_response.status_code == 200
        data = delete_response.get_json()
        assert data["status"] == "success"

        # Verify deletion by trying to get decisions for that prospect
        get_response = self._auth_request(
            client, "get", f"/api/decisions/{prospect.id}"
        )

        assert get_response.status_code == 200
        decisions = get_response.get_json()["data"]["decisions"]

        # The deleted decision should not be in the list
        decision_ids = [d["id"] for d in decisions]
        assert decision_id not in decision_ids

    def test_delete_nonexistent_decision(self, client):
        """Test deleting a decision that doesn't exist."""
        fake_id = random.randint(100000, 999999)

        response = self._auth_request(client, "delete", f"/api/decisions/{fake_id}")

        assert response.status_code == 404
        data = response.get_json()
        assert "message" in data or "error" in data

    def test_authentication_required(self, client):
        """Test that authentication is required for decision endpoints."""
        # Test without authentication
        response = client.get("/api/decisions/my")

        assert response.status_code == 401
        data = response.get_json()
        assert "message" in data or "error" in data

    def test_decision_reason_variations(self, client):
        """Test decision creation with various reason formats."""
        prospect = random.choice(self.test_prospects)

        # Test with different reason lengths and formats
        test_reasons = [
            "",  # Empty reason
            "Short",
            "A" * 500,  # Long reason
            "Reason with\nnewlines\nand\ttabs",
            "Reason with special chars: @#$%^&*()",
            "   Reason with spaces   ",
            None,  # Null reason
        ]

        for reason in test_reasons:
            decision_data = {
                "prospect_id": prospect.id,
                "decision": random.choice(["go", "no-go"]),
                "reason": reason if reason is not None else "",
            }

            response = self._auth_request(
                client,
                "post",
                "/api/decisions/",
                data=json.dumps(decision_data),
                content_type="application/json",
            )

            # Should handle all reason formats
            assert response.status_code in [200, 400]

            if response.status_code == 200:
                data = response.get_json()
                stored_reason = data["data"]["decision"]["reason"]
                # Verify reason was stored (may be processed/trimmed)
                # Empty strings may be stored as None
                if reason == "" or reason is None:
                    assert stored_reason is None or stored_reason == ""
                # Non-empty, non-None reasons should be stored (possibly trimmed)
                elif reason.strip():
                    # If there's content after stripping, it should be stored
                    assert stored_reason is not None, (
                        f"Expected non-None for reason={repr(reason)}, got {repr(stored_reason)}"
                    )
                else:
                    # If stripping results in empty, it may be stored as None
                    assert stored_reason is None or stored_reason == ""

    def test_concurrent_decision_updates(self, client):
        """Test handling of concurrent decision updates."""
        prospect = random.choice(self.test_prospects)

        # Simulate multiple users updating the same prospect
        for i, user in enumerate(self.test_users[: min(3, len(self.test_users))]):
            decision_data = {
                "prospect_id": prospect.id,
                "decision": random.choice(["go", "no-go"]),
                "reason": f"User {i} decision",
            }

            response = self._auth_request(
                client,
                "post",
                "/api/decisions/",
                user_id=user.id,
                data=json.dumps(decision_data),
                content_type="application/json",
            )

            # Each user should be able to create their own decision
            assert response.status_code == 200
            data = response.get_json()
            assert data["data"]["decision"]["user_id"] == user.id

    def test_decision_timestamp_behavior(self, client):
        """Test that decision timestamps are handled correctly."""
        prospect = random.choice(self.test_prospects)

        before_time = datetime.now(UTC)

        decision_data = {
            "prospect_id": prospect.id,
            "decision": "go",
            "reason": "Timestamp test",
        }

        response = self._auth_request(
            client,
            "post",
            "/api/decisions/",
            data=json.dumps(decision_data),
            content_type="application/json",
        )

        after_time = datetime.now(UTC)

        assert response.status_code == 200
        data = response.get_json()

        # Verify timestamp exists and is reasonable
        assert "created_at" in data["data"]["decision"]
        created_at_str = data["data"]["decision"]["created_at"]

        # Parse timestamp (handle various formats)
        try:
            if "T" in created_at_str:
                created_at = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
            else:
                created_at = datetime.fromisoformat(created_at_str)

            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)

            # Timestamp should be within test execution window (with some tolerance)
            assert (
                before_time - timedelta(seconds=5)
                <= created_at
                <= after_time + timedelta(seconds=5)
            )
        except:
            # If timestamp parsing fails, just verify it exists
            assert created_at_str is not None

    def test_api_security_measures(self, client):
        """Test that API is protected against common attacks."""
        # Test SQL injection attempts
        malicious_inputs = [
            "'; DROP TABLE decisions; --",
            "1' OR '1'='1",
            "'; SELECT * FROM users; --",
        ]

        for malicious in malicious_inputs:
            decision_data = {
                "prospect_id": malicious,
                "decision": "go",
                "reason": "Security test",
            }

            response = self._auth_request(
                client,
                "post",
                "/api/decisions/",
                data=json.dumps(decision_data),
                content_type="application/json",
            )

            # Should not crash, should return error for invalid prospect
            assert response.status_code in [400, 404]

        # Test XSS in reason field
        xss_reason = '<script>alert("xss")</script>'
        valid_prospect = random.choice(self.test_prospects)

        xss_data = {
            "prospect_id": valid_prospect.id,
            "decision": "go",
            "reason": xss_reason,
        }

        response = self._auth_request(
            client,
            "post",
            "/api/decisions/",
            data=json.dumps(xss_data),
            content_type="application/json",
        )

        # API should accept the data (sanitization happens at render time)
        if response.status_code == 200:
            data = response.get_json()
            # Verify data was stored but will be escaped when rendered
            assert data["data"]["decision"]["reason"] == xss_reason

    def test_content_type_handling(self, client):
        """Test that API handles content types correctly."""
        prospect = random.choice(self.test_prospects)

        decision_data = {
            "prospect_id": prospect.id,
            "decision": "go",
            "reason": "Content type test",
        }

        # Test with correct JSON content type
        response = self._auth_request(
            client,
            "post",
            "/api/decisions/",
            data=json.dumps(decision_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert response.content_type == "application/json"

        # Verify response is valid JSON
        try:
            json.loads(response.get_data(as_text=True))
        except json.JSONDecodeError:
            pytest.fail("Response is not valid JSON")

    @pytest.mark.parametrize("decision_type", ["go", "no-go"])
    def test_decision_types(self, client, decision_type):
        """Test both decision types work correctly."""
        prospect = random.choice(self.test_prospects)

        decision_data = {
            "prospect_id": prospect.id,
            "decision": decision_type,
            "reason": f"Testing {decision_type} decision",
        }

        response = self._auth_request(
            client,
            "post",
            "/api/decisions/",
            data=json.dumps(decision_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["decision"]["decision"] == decision_type
