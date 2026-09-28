"""
Integration tests for API workflows covering user journeys and cross-layer interactions.
These tests use a real database and test complete workflows from API to database.
Following production-level testing principles:
- No hardcoded expected values
- Tests verify behavior, not specific data
- Uses real database operations
- Mocks only external dependencies
"""

import json
import os
import random
import string
import tempfile
from datetime import UTC

UTC = UTC
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from app import create_app
from app.database import db
from app.database.models import DataSource, Prospect


def generate_random_string(length=10):
    """Generate random string for test data."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_random_prospect_data(source_id):
    """Generate random prospect data for testing."""
    agencies = [
        "Department of Defense",
        "Department of Energy",
        "Health and Human Services",
        "Department of Commerce",
        "Department of State",
        "Social Security Administration",
    ]
    naics_codes = ["541511", "541512", "541519", "517311", "236220", "541611"]

    value_min = random.randint(10000, 100000)
    value_max = value_min + random.randint(50000, 500000)

    return {
        "id": generate_random_string(12),
        "title": f"{random.choice(['Software', 'Hardware', 'Services', 'Research'])} {generate_random_string(6)}",
        "description": " ".join([f"word{i}" for i in random.sample(range(100), 10)]),
        "agency": random.choice(agencies),
        "posted_date": date.today() - timedelta(days=random.randint(1, 30)),
        "estimated_value": random.randint(value_min, value_max),
        "estimated_value_text": f"${value_min:,} - ${value_max:,}",
        "naics": random.choice(naics_codes),
        "source_id": source_id,
        "source_file": f"test_{generate_random_string(8)}.json",
        "loaded_at": datetime.now(UTC),
    }


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
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        # Create all tables
        db.create_all()

        # Create a test data source with random data
        source_name = f"Agency_{generate_random_string(6)}"
        test_source = DataSource(
            name=source_name,
            url=f"https://{generate_random_string(8)}.gov",
            scraper_class=f"{generate_random_string(10)}Scraper",
            active=random.choice([True, False]),
        )
        db.session.add(test_source)
        db.session.commit()

        # Store ID for tests
        app.config["TEST_SOURCE_ID"] = test_source.id
        app.config["TEST_SOURCE_NAME"] = source_name
        app.config["TEST_USER_ID"] = generate_random_string(12)
        app.config["TEST_USERNAME"] = f"user_{generate_random_string(6)}"

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
    """Create an authenticated test client with dynamic user data."""
    # Mock authentication for testing
    with patch("app.api.auth.get_current_user") as mock_auth:
        user_role = random.choice(["user", "admin", "analyst"])
        mock_auth.return_value = {
            "id": app.config["TEST_USER_ID"],
            "username": app.config["TEST_USERNAME"],
            "role": user_role,
        }
        app.config["TEST_USER_ROLE"] = user_role
        yield client


class TestProspectWorkflow:
    """Test complete prospect management workflows with dynamic data."""

    def test_prospect_creation_and_retrieval_workflow(self, app, client):
        """Test creating prospects and retrieving them through the API with dynamic data."""
        with app.app_context():
            # Create random number of test prospects
            num_prospects = random.randint(2, 5)
            created_prospects = []

            for _ in range(num_prospects):
                prospect_data = generate_random_prospect_data(
                    app.config["TEST_SOURCE_ID"]
                )
                prospect = Prospect(**prospect_data)
                db.session.add(prospect)
                created_prospects.append(prospect_data)

            db.session.commit()

        # Test API retrieval - basic pagination
        response = client.get("/api/prospects")
        assert response.status_code == 200

        data = response.get_json()
        assert "prospects" in data
        assert "pagination" in data
        assert len(data["prospects"]) == num_prospects
        assert data["pagination"]["total_items"] == num_prospects

        # Verify prospect data structure (behavioral test)
        if data["prospects"]:
            prospect = data["prospects"][0]
            required_fields = [
                "id",
                "title",
                "description",
                "agency",
                "posted_date",
                "estimated_value",
                "naics",
                "loaded_at",
            ]
            for field in required_fields:
                assert field in prospect
                assert prospect[field] is not None or field in [
                    "description",
                    "naics",
                ]  # Some fields can be null

    def test_prospect_filtering_workflow(self, app, client):
        """Test prospect filtering through API with various filter combinations and dynamic data."""
        with app.app_context():
            # Create diverse test data with controlled attributes
            num_prospects = random.randint(5, 10)
            agencies = [
                "Department of Defense",
                "Department of Commerce",
                "Health and Human Services",
            ]
            naics_codes = ["541511", "541512", "541519"]

            created_prospects = []
            agency_counts = dict.fromkeys(agencies, 0)
            naics_counts = dict.fromkeys(naics_codes, 0)
            keyword_prospects = []

            for i in range(num_prospects):
                agency = random.choice(agencies)
                naics = random.choice(naics_codes)

                # Add keyword to some prospects
                has_keyword = random.random() > 0.5
                keyword = "SpecialKeyword" if has_keyword else ""

                prospect_data = {
                    "id": generate_random_string(12),
                    "title": f"{keyword} {random.choice(['Software', 'Hardware'])} {generate_random_string(6)}",
                    "description": f"Description with {keyword}"
                    if has_keyword
                    else "Regular description",
                    "agency": agency,
                    "naics": naics,
                    "estimated_value": random.randint(10000, 500000),
                    "posted_date": date.today() - timedelta(days=random.randint(1, 30)),
                    "source_id": app.config["TEST_SOURCE_ID"],
                    "source_file": "filter_test.json",
                    "loaded_at": datetime.now(UTC),
                }

                # Randomly add AI enhancement to some
                if random.random() > 0.6:
                    prospect_data["ai_enhanced_title"] = (
                        f"Enhanced: {prospect_data['title']}"
                    )
                    prospect_data["ollama_processed_at"] = datetime.now(UTC)

                prospect = Prospect(**prospect_data)
                db.session.add(prospect)

                created_prospects.append(prospect_data)
                agency_counts[agency] += 1
                naics_counts[naics] += 1
                if has_keyword:
                    keyword_prospects.append(prospect_data)

            db.session.commit()

        # Test NAICS code filtering with a code that exists
        test_naics = random.choice([n for n in naics_codes if naics_counts[n] > 0])
        response = client.get(f"/api/prospects?naics={test_naics}")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["prospects"]) == naics_counts[test_naics]
        for prospect in data["prospects"]:
            assert prospect["naics"] == test_naics

        # Test agency filtering with an agency that exists
        test_agency = random.choice([a for a in agencies if agency_counts[a] > 0])
        response = client.get(f"/api/prospects?agency={test_agency}")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["prospects"]) == agency_counts[test_agency]
        for prospect in data["prospects"]:
            assert prospect["agency"] == test_agency

        # Test keyword search if we have keyword prospects
        if keyword_prospects:
            response = client.get("/api/prospects?keywords=SpecialKeyword")
            assert response.status_code == 200
            data = response.get_json()
            assert len(data["prospects"]) == len(keyword_prospects)

    def test_prospect_pagination_workflow(self, app, client):
        """Test prospect pagination with various page sizes and navigation using dynamic data."""
        with app.app_context():
            # Create random number of test prospects for pagination testing
            total_prospects = random.randint(15, 35)

            for i in range(total_prospects):
                prospect_data = generate_random_prospect_data(
                    app.config["TEST_SOURCE_ID"]
                )
                prospect = Prospect(**prospect_data)
                db.session.add(prospect)

            db.session.commit()

        # Test default pagination (page 1, limit 10)
        response = client.get("/api/prospects")
        assert response.status_code == 200
        data = response.get_json()

        default_limit = 10
        expected_first_page = min(default_limit, total_prospects)
        assert len(data["prospects"]) == expected_first_page
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["total_items"] == total_prospects

        total_pages = (total_prospects + default_limit - 1) // default_limit
        assert data["pagination"]["total_pages"] == total_pages

        if total_prospects > default_limit:
            assert data["pagination"]["has_next"] is True
        assert data["pagination"]["has_prev"] is False

        # Test page 2 if there are enough items
        if total_prospects > default_limit:
            response = client.get("/api/prospects?page=2")
            assert response.status_code == 200
            data = response.get_json()

            expected_second_page = min(default_limit, total_prospects - default_limit)
            assert len(data["prospects"]) == expected_second_page
            assert data["pagination"]["page"] == 2
            assert data["pagination"]["has_prev"] is True

            if total_prospects > 2 * default_limit:
                assert data["pagination"]["has_next"] is True
            else:
                assert data["pagination"]["has_next"] is False

        # Test custom page size
        custom_limit = random.randint(3, 8)
        response = client.get(f"/api/prospects?limit={custom_limit}")
        assert response.status_code == 200
        data = response.get_json()

        expected_custom_page = min(custom_limit, total_prospects)
        assert len(data["prospects"]) == expected_custom_page

        custom_total_pages = (total_prospects + custom_limit - 1) // custom_limit
        assert data["pagination"]["total_pages"] == custom_total_pages

        # Test out of range page
        response = client.get("/api/prospects?page=999")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["prospects"]) == 0


class TestDecisionWorkflow:
    """Test complete decision management workflows with dynamic data."""

    def test_decision_creation_and_retrieval_workflow(self, app, auth_client):
        """Test creating and retrieving decisions through the API with dynamic data."""
        with app.app_context():
            # Create a test prospect for decisions
            prospect_data = generate_random_prospect_data(app.config["TEST_SOURCE_ID"])
            prospect = Prospect(**prospect_data)
            db.session.add(prospect)
            db.session.commit()
            prospect_id = prospect_data["id"]

        # Create a random decision
        decision_type = random.choice(["go", "no-go"])
        reasons = [
            "Good fit for our services and capabilities",
            "Aligns with strategic goals",
            "Strong competitive position",
            "Outside our core competencies",
            "Resource constraints",
        ]

        decision_data = {
            "prospect_id": prospect_id,
            "decision": decision_type,
            "reason": random.choice(reasons),
        }

        response = auth_client.post(
            "/api/decisions/",
            data=json.dumps(decision_data),
            content_type="application/json",
        )
        assert response.status_code == 201

        created_decision = response.get_json()
        assert created_decision["data"]["decision"]["decision"] == decision_type
        assert created_decision["data"]["decision"]["prospect_id"] == prospect_id
        decision_id = created_decision["data"]["decision"]["id"]

        # Retrieve decisions for the prospect
        response = auth_client.get(f"/api/decisions/{prospect_id}")
        assert response.status_code == 200

        decisions_data = response.get_json()
        assert decisions_data["data"]["total_decisions"] == 1
        assert len(decisions_data["data"]["decisions"]) == 1
        assert decisions_data["data"]["decisions"][0]["decision"] == decision_type

        # Test updating decision with opposite type
        opposite_decision = "no-go" if decision_type == "go" else "go"
        update_data = {
            "prospect_id": prospect_id,
            "decision": opposite_decision,
            "reason": random.choice(reasons),
        }

        response = auth_client.post(
            "/api/decisions/",
            data=json.dumps(update_data),
            content_type="application/json",
        )
        assert response.status_code == 201

        # Should now have 2 decisions (history is kept)
        response = auth_client.get(f"/api/decisions/{prospect_id}")
        assert response.status_code == 200
        decisions_data = response.get_json()
        assert decisions_data["data"]["total_decisions"] == 2

        # Most recent should be the opposite decision
        latest_decision = max(
            decisions_data["data"]["decisions"], key=lambda d: d["created_at"]
        )
        assert latest_decision["decision"] == opposite_decision

    def test_decision_stats_workflow(self, app, auth_client):
        """Test decision statistics aggregation with dynamic data."""
        with app.app_context():
            # Create random number of prospects and decisions
            num_decisions = random.randint(3, 8)
            go_count = 0
            no_go_count = 0

            for i in range(num_decisions):
                # Create prospect
                prospect_data = generate_random_prospect_data(
                    app.config["TEST_SOURCE_ID"]
                )
                prospect = Prospect(**prospect_data)
                db.session.add(prospect)
                db.session.commit()

                # Create random decision
                decision_type = random.choice(["go", "no-go"])
                if decision_type == "go":
                    go_count += 1
                else:
                    no_go_count += 1

                reasons = [
                    "Good opportunity",
                    "Excellent fit",
                    "Not aligned with strategy",
                    "Strong potential",
                    "Too much risk",
                ]

                decision_data = {
                    "prospect_id": prospect_data["id"],
                    "decision": decision_type,
                    "reason": random.choice(reasons),
                }

                response = auth_client.post(
                    "/api/decisions/",
                    data=json.dumps(decision_data),
                    content_type="application/json",
                )
                assert response.status_code == 201

        # Get decision statistics
        response = auth_client.get("/api/decisions/stats")
        assert response.status_code == 200

        stats = response.get_json()["data"]
        assert stats["total_decisions"] == num_decisions
        assert stats["go_decisions"] == go_count
        assert stats["no_go_decisions"] == no_go_count
        assert len(stats["decisions_by_user"]) >= 1
        assert len(stats["recent_decisions"]) >= 1

        # Verify user has correct decision count
        user_stats = next(
            (
                u
                for u in stats["decisions_by_user"]
                if u["username"] == app.config["TEST_USERNAME"]
            ),
            None,
        )
        if user_stats:
            assert user_stats["decision_count"] == num_decisions


class TestDataSourceWorkflow:
    """Test data source management workflows with dynamic data."""

    def test_data_source_listing_workflow(self, app, client):
        """Test retrieving data sources through the API."""
        response = client.get("/api/data-sources")
        assert response.status_code == 200

        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1  # Should have at least the test source

        # Verify data source structure
        if data:
            source = data[0]
            required_fields = [
                "id",
                "name",
                "url",
                "scraper_class",
                "active",
                "last_scraped",
            ]
            for field in required_fields:
                assert field in source

            # Find our test source
            test_source = next(
                (s for s in data if s["name"] == app.config["TEST_SOURCE_NAME"]), None
            )
            if test_source:
                assert test_source["name"] == app.config["TEST_SOURCE_NAME"]
                assert isinstance(test_source["active"], bool)


class TestHealthWorkflow:
    """Test application health and status workflows."""

    def test_health_check_workflow(self, app, client):
        """Test health check endpoints."""
        response = client.get("/api/health")
        assert response.status_code == 200

        health_data = response.get_json()
        assert "status" in health_data
        assert "database" in health_data
        assert "timestamp" in health_data

        # Should be healthy if we got this far
        assert health_data["status"] in ["healthy", "degraded"]
        assert health_data["database"] in ["connected", "ok"]

    def test_database_status_workflow(self, app, client):
        """Test database connectivity verification."""
        response = client.get("/api/health/database")
        assert response.status_code == 200

        db_health = response.get_json()
        assert "status" in db_health
        assert "connection" in db_health
        assert "prospect_count" in db_health

        assert db_health["status"] in ["healthy", "ok"]
        assert db_health["connection"] in ["ok", "connected"]
        assert isinstance(db_health["prospect_count"], int)
        assert db_health["prospect_count"] >= 0


class TestErrorHandlingWorkflow:
    """Test error handling across API endpoints."""

    def test_prospect_not_found_workflow(self, app, client):
        """Test handling of non-existent prospect requests."""
        non_existent_id = generate_random_string(20)
        response = client.get(f"/api/prospects/{non_existent_id}")
        assert response.status_code == 404

        error_data = response.get_json()
        assert "error" in error_data or "message" in error_data

    def test_invalid_pagination_workflow(self, app, client):
        """Test handling of invalid pagination parameters."""
        # Test negative page
        response = client.get("/api/prospects?page=-1")
        assert response.status_code in [400, 200]  # May handle gracefully

        # Test invalid limit
        response = client.get("/api/prospects?limit=0")
        assert response.status_code in [400, 200]  # May handle gracefully

        # Test excessive limit
        response = client.get("/api/prospects?limit=1000")
        assert response.status_code in [400, 200]  # May have max limit

    def test_malformed_decision_workflow(self, app, auth_client):
        """Test handling of malformed decision requests."""
        # Missing required fields
        response = auth_client.post(
            "/api/decisions/", data=json.dumps({}), content_type="application/json"
        )
        assert response.status_code in [400, 422]  # Bad request or unprocessable

        # Invalid decision type
        invalid_decision = {
            "prospect_id": generate_random_string(12),
            "decision": f"invalid-{generate_random_string(6)}",
            "reason": "Test reason",
        }

        response = auth_client.post(
            "/api/decisions/",
            data=json.dumps(invalid_decision),
            content_type="application/json",
        )
        assert response.status_code in [400, 422]


class TestConcurrencyWorkflow:
    """Test concurrent operations and data consistency with dynamic data."""

    def test_concurrent_decision_creation_workflow(self, app, auth_client):
        """Test handling of concurrent decision creation for same prospect."""
        with app.app_context():
            # Create test prospect
            prospect_data = generate_random_prospect_data(app.config["TEST_SOURCE_ID"])
            prospect = Prospect(**prospect_data)
            db.session.add(prospect)
            db.session.commit()
            prospect_id = prospect_data["id"]

        # Create multiple decisions rapidly with random types
        num_decisions = random.randint(2, 5)
        decisions = []

        for i in range(num_decisions):
            decision_type = random.choice(["go", "no-go"])
            decision_data = {
                "prospect_id": prospect_id,
                "decision": decision_type,
                "reason": f"Decision {i + 1}: {generate_random_string(10)}",
            }
            decisions.append(decision_data)

        responses = []
        for decision_data in decisions:
            response = auth_client.post(
                "/api/decisions/",
                data=json.dumps(decision_data),
                content_type="application/json",
            )
            responses.append(response)

        # All should succeed
        for response in responses:
            assert response.status_code == 201

        # Verify all decisions were recorded
        response = auth_client.get(f"/api/decisions/{prospect_id}")
        assert response.status_code == 200

        decisions_data = response.get_json()
        assert decisions_data["data"]["total_decisions"] == num_decisions


if __name__ == "__main__":
    pytest.main([__file__])
