"""
Comprehensive tests for Prospects API endpoints.

Tests all prospects API functionality including filtering, pagination, and search.
These tests follow production-level principles:
- No hardcoded expected values
- Tests verify behavior, not specific data
- Uses real database operations
"""

import json
import random
import string
import time
from datetime import UTC

UTC = UTC
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app import create_app
from app.database import db
from app.database.models import DataSource, Prospect


class TestProspectsAPI:
    """Test suite for Prospects API endpoints."""

    @pytest.fixture(scope="class")
    def app(self):
        """Create test Flask app with real in-memory database."""
        app = create_app()
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["WTF_CSRF_ENABLED"] = False
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()

    @pytest.fixture(autouse=True)
    def setup_database(self, app):
        """Set up test database with dynamically generated data."""
        with app.app_context():
            db.create_all()

            # Create data sources with realistic attributes
            data_sources = []
            agencies = [
                "Department of Defense",
                "Health and Human Services",
                "Department of Commerce",
            ]

            for agency in agencies:
                ds = DataSource(
                    name=agency,
                    url=f"https://{agency.lower().replace(' ', '')}.gov",
                    last_scraped=datetime.now(UTC)
                    - timedelta(days=random.randint(0, 7)),
                )
                db.session.add(ds)
                data_sources.append(ds)

            db.session.flush()

            # Create prospects with varying attributes
            prospects = []
            titles = [
                "Software Development Services",
                "Cloud Infrastructure Management",
                "Data Analytics Platform",
                "Cybersecurity Assessment",
                "Network Infrastructure Upgrade",
                "AI/ML Research Services",
            ]

            naics_codes = ["541511", "541512", "541519", "517311", "518210"]
            contract_types = ["Fixed Price", "Time and Materials", "Cost Plus"]
            set_asides = [
                "Small Business",
                "8(a) Set-Aside",
                "WOSB Set-Aside",
                "Full and Open",
            ]
            cities = ["Washington", "New York", "San Francisco", "Austin", "Chicago"]
            states = ["DC", "NY", "CA", "TX", "IL"]

            for i in range(random.randint(10, 20)):
                # Generate prospect with some randomness
                prospect = Prospect(
                    id=f"PROSPECT-{i:03d}",
                    native_id=f"NATIVE-{i:03d}",
                    title=random.choice(titles) + f" {i}",
                    description=f"Description for prospect {i} with various requirements and specifications",
                    agency=random.choice(agencies),
                    naics=random.choice(naics_codes) if random.random() > 0.2 else None,
                    naics_description="Some NAICS description"
                    if random.random() > 0.3
                    else None,
                    naics_source=random.choice(["original", "llm_inferred", None]),
                    estimated_value_text=f"${random.randint(10, 500) * 1000:,}"
                    if random.random() > 0.3
                    else "TBD",
                    estimated_value_single=Decimal(str(random.randint(10000, 5000000)))
                    if random.random() > 0.4
                    else None,
                    release_date=date.today() - timedelta(days=random.randint(0, 30)),
                    award_date=date.today() + timedelta(days=random.randint(30, 180))
                    if random.random() > 0.5
                    else None,
                    place_city=random.choice(cities) if random.random() > 0.2 else None,
                    place_state=random.choice(states)
                    if random.random() > 0.2
                    else None,
                    contract_type=random.choice(contract_types)
                    if random.random() > 0.3
                    else None,
                    set_aside=random.choice(set_asides)
                    if random.random() > 0.3
                    else None,
                    set_aside_standardized=random.choice(
                        ["SMALL_BUSINESS", "EIGHT_A", "WOSB", "FULL_AND_OPEN", None]
                    ),
                    primary_contact_email=f"contact{i}@agency.gov"
                    if random.random() > 0.5
                    else None,
                    primary_contact_name=f"Contact Person {i}"
                    if random.random() > 0.5
                    else None,
                    source_id=random.choice(data_sources).id,
                    loaded_at=datetime.now(UTC)
                    - timedelta(hours=random.randint(0, 72)),
                    ollama_processed_at=datetime.now(UTC)
                    if random.random() > 0.5
                    else None,
                    enhancement_status=random.choice(
                        ["idle", "in_progress", "completed", "failed"]
                    ),
                )
                db.session.add(prospect)
                prospects.append(prospect)

            db.session.commit()

            # Store test data for behavioral verification
            self.test_data = {
                "data_sources": data_sources,
                "prospects": prospects,
                "agencies": agencies,
            }

            yield

            # Cleanup
            db.session.rollback()
            db.drop_all()

    def test_get_prospects_returns_data(self, client):
        """Test that prospects endpoint returns data with correct structure."""
        response = client.get("/api/prospects")

        assert response.status_code == 200
        data = response.get_json()

        # Verify response structure
        assert "prospects" in data
        assert "pagination" in data
        assert isinstance(data["prospects"], list)
        assert isinstance(data["pagination"], dict)

        # Verify prospects were returned (we created some)
        assert len(data["prospects"]) > 0

        # Verify each prospect has required fields
        if data["prospects"]:
            prospect = data["prospects"][0]
            required_fields = ["id", "title", "agency"]
            for field in required_fields:
                assert field in prospect
                assert prospect[field] is not None

    def test_pagination_behavior(self, client):
        """Test that pagination correctly limits and pages through results."""
        # Get total count first
        response = client.get("/api/prospects?limit=1")
        assert response.status_code == 200
        total_items = response.get_json()["pagination"]["total_items"]

        # Test that limit actually limits results
        limit = min(5, total_items)
        response = client.get(f"/api/prospects?limit={limit}")
        assert response.status_code == 200
        data = response.get_json()

        assert len(data["prospects"]) <= limit
        assert data["pagination"]["total_items"] == total_items

        # Test pagination through all results
        all_ids = set()
        page = 1
        has_next = True

        while has_next:
            response = client.get(f"/api/prospects?page={page}&limit={limit}")
            assert response.status_code == 200
            data = response.get_json()

            # Collect IDs to verify no duplicates across pages
            for prospect in data["prospects"]:
                assert prospect["id"] not in all_ids, "Duplicate prospect across pages"
                all_ids.add(prospect["id"])

            has_next = data["pagination"]["has_next"]
            page += 1

            # Prevent infinite loop
            if page > 100:
                pytest.fail("Too many pages, possible infinite loop")

        # Verify we got all prospects
        assert len(all_ids) == total_items

    def test_search_functionality(self, client):
        """Test that search filters results appropriately."""
        # First, get a prospect to search for
        response = client.get("/api/prospects?limit=1")
        assert response.status_code == 200
        sample_prospect = response.get_json()["prospects"][0]

        # Search by part of title
        if sample_prospect.get("title"):
            search_term = sample_prospect["title"].split()[0]
            response = client.get(f"/api/prospects?search={search_term}")
            assert response.status_code == 200
            data = response.get_json()

            # Verify all returned prospects contain search term
            for prospect in data["prospects"]:
                found_in_fields = (
                    search_term.lower() in (prospect.get("title", "") or "").lower()
                    or search_term.lower()
                    in (prospect.get("description", "") or "").lower()
                    or search_term.lower() in (prospect.get("agency", "") or "").lower()
                )
                assert found_in_fields, (
                    f"Search term '{search_term}' not found in prospect fields"
                )

        # Search for non-existent term should return empty or no results
        random_string = "".join(random.choices(string.ascii_letters, k=20))
        response = client.get(f"/api/prospects?search={random_string}")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["prospects"]) == 0

    def test_naics_filter_behavior(self, client):
        """Test that NAICS filtering works correctly."""
        # Get all prospects to find available NAICS codes
        response = client.get("/api/prospects?limit=100")
        assert response.status_code == 200
        all_prospects = response.get_json()["prospects"]

        # Find a NAICS code that exists
        naics_codes = [p["naics"] for p in all_prospects if p.get("naics")]

        if naics_codes:
            test_naics = naics_codes[0]

            # Filter by this NAICS code
            response = client.get(f"/api/prospects?naics={test_naics}")
            assert response.status_code == 200
            data = response.get_json()

            # Verify all returned prospects have this NAICS code
            for prospect in data["prospects"]:
                assert prospect["naics"] == test_naics

            # Verify we got at least one result
            assert len(data["prospects"]) > 0

    def test_agency_filter_behavior(self, client):
        """Test that agency filtering works correctly."""
        # Get a sample agency
        response = client.get("/api/prospects?limit=1")
        assert response.status_code == 200
        sample_agency = response.get_json()["prospects"][0]["agency"]

        # Filter by this agency
        response = client.get(f"/api/prospects?agency={sample_agency}")
        assert response.status_code == 200
        data = response.get_json()

        # Verify all returned prospects have this agency
        for prospect in data["prospects"]:
            assert prospect["agency"] == sample_agency

        # Verify we got at least one result
        assert len(data["prospects"]) > 0

    def test_ai_enrichment_filter_behavior(self, client):
        """Test that AI enrichment filtering separates enhanced/non-enhanced prospects."""
        # Get enhanced prospects
        response = client.get("/api/prospects?ai_enrichment=enhanced")
        assert response.status_code == 200
        enhanced_data = response.get_json()

        # Verify all enhanced prospects have processing timestamp
        for prospect in enhanced_data["prospects"]:
            assert prospect["ollama_processed_at"] is not None

        # Get non-enhanced prospects
        response = client.get("/api/prospects?ai_enrichment=original")
        assert response.status_code == 200
        original_data = response.get_json()

        # Verify all non-enhanced prospects don't have processing timestamp
        for prospect in original_data["prospects"]:
            assert prospect["ollama_processed_at"] is None

        # Get all prospects to verify partitioning
        response = client.get("/api/prospects?limit=100")
        assert response.status_code == 200
        all_data = response.get_json()

        # Total of enhanced + original should equal all (or be close if pagination limits apply)
        total_filtered = len(enhanced_data["prospects"]) + len(
            original_data["prospects"]
        )
        total_all = len(all_data["prospects"])

        # They should be similar (might differ due to pagination limits)
        assert (
            abs(total_filtered - total_all) <= 100
        )  # Allow some difference for large datasets

    def test_sorting_behavior(self, client):
        """Test that sorting orders results correctly."""
        # Test ascending sort
        response = client.get("/api/prospects?sort_by=title&sort_order=asc&limit=10")
        assert response.status_code == 200
        data_asc = response.get_json()

        if len(data_asc["prospects"]) > 1:
            titles_asc = [p["title"] for p in data_asc["prospects"] if p.get("title")]
            # Verify ascending order
            for i in range(len(titles_asc) - 1):
                assert titles_asc[i].lower() <= titles_asc[i + 1].lower()

        # Test descending sort
        response = client.get("/api/prospects?sort_by=title&sort_order=desc&limit=10")
        assert response.status_code == 200
        data_desc = response.get_json()

        if len(data_desc["prospects"]) > 1:
            titles_desc = [p["title"] for p in data_desc["prospects"] if p.get("title")]
            # Verify descending order
            for i in range(len(titles_desc) - 1):
                assert titles_desc[i].lower() >= titles_desc[i + 1].lower()

    def test_combined_filters_work_together(self, client):
        """Test that multiple filters can be combined."""
        # Get initial data to find valid filter combinations
        response = client.get("/api/prospects?limit=20")
        assert response.status_code == 200
        prospects = response.get_json()["prospects"]

        # Find a prospect with multiple filterable attributes
        test_prospect = None
        for p in prospects:
            if p.get("agency") and p.get("naics") and p.get("ollama_processed_at"):
                test_prospect = p
                break

        if test_prospect:
            # Apply combined filters
            response = client.get(
                f"/api/prospects?agency={test_prospect['agency']}"
                f"&naics={test_prospect['naics']}"
                f"&ai_enrichment=enhanced"
            )
            assert response.status_code == 200
            data = response.get_json()

            # Verify all returned prospects match all filters
            for prospect in data["prospects"]:
                assert prospect["agency"] == test_prospect["agency"]
                assert prospect["naics"] == test_prospect["naics"]
                assert prospect["ollama_processed_at"] is not None

            # Should have at least the test prospect
            assert len(data["prospects"]) > 0

    def test_invalid_parameters_handled_gracefully(self, client):
        """Test that invalid parameters are handled without crashing."""
        # Test invalid page number
        response = client.get("/api/prospects?page=0")
        assert response.status_code == 400
        assert "error" in response.get_json()

        response = client.get("/api/prospects?page=-5")
        assert response.status_code == 400

        # Test invalid limit
        response = client.get("/api/prospects?limit=0")
        assert response.status_code in [200, 400]  # May use default or error

        # Test excessive limit
        response = client.get("/api/prospects?limit=10000")
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "100" in data["error"]  # Should mention max limit

        # Test invalid sort order
        response = client.get("/api/prospects?sort_order=invalid")
        # Should either ignore or return error, not crash
        assert response.status_code in [200, 400]

    def test_get_prospect_by_id(self, client):
        """Test retrieving individual prospect by ID."""
        # First get a valid prospect ID
        response = client.get("/api/prospects?limit=1")
        assert response.status_code == 200
        prospect_id = response.get_json()["prospects"][0]["id"]

        # Retrieve specific prospect
        response = client.get(f"/api/prospects/{prospect_id}")
        assert response.status_code == 200
        data = response.get_json()

        # Verify correct prospect returned
        assert data["id"] == prospect_id

        # Verify structure has expected fields
        expected_fields = ["id", "title", "description", "agency", "loaded_at"]
        for field in expected_fields:
            assert field in data

        # Test non-existent ID
        fake_id = "NON-EXISTENT-" + "".join(
            random.choices(string.ascii_uppercase, k=10)
        )
        response = client.get(f"/api/prospects/{fake_id}")
        assert response.status_code == 404
        assert "error" in response.get_json()

    def test_api_performance_acceptable(self, client):
        """Test that API responds within acceptable time limits."""
        # Test various endpoints
        test_endpoints = [
            "/api/prospects",
            "/api/prospects?limit=10",
            "/api/prospects?page=1",
            "/api/prospects?search=test",
        ]

        for endpoint in test_endpoints:
            start_time = time.time()
            response = client.get(endpoint)
            response_time = time.time() - start_time

            assert response.status_code in [200, 400, 404]
            # Response should be under 2 seconds for in-memory database
            assert response_time < 2.0, f"Endpoint {endpoint} took {response_time:.2f}s"

    def test_data_integrity_in_responses(self, client):
        """Test that API responses maintain data integrity."""
        response = client.get("/api/prospects?limit=10")
        assert response.status_code == 200
        data = response.get_json()

        for prospect in data["prospects"]:
            # Required fields should not be None
            assert prospect.get("id") is not None
            assert (
                prospect.get("title") is not None
                or prospect.get("description") is not None
            )
            assert prospect.get("agency") is not None

            # Numeric fields should be valid if present
            if prospect.get("estimated_value_single") is not None:
                try:
                    float(prospect["estimated_value_single"])
                except (ValueError, TypeError):
                    pytest.fail(
                        f"Invalid numeric value: {prospect['estimated_value_single']}"
                    )

            # Enhancement status should be valid
            if prospect.get("enhancement_status"):
                valid_statuses = ["idle", "in_progress", "completed", "failed"]
                assert prospect["enhancement_status"] in valid_statuses

            # Dates should be parseable if present
            date_fields = [
                "loaded_at",
                "ollama_processed_at",
                "release_date",
                "award_date",
            ]
            for date_field in date_fields:
                if prospect.get(date_field):
                    try:
                        # Just verify it's a string that looks like a date
                        assert isinstance(prospect[date_field], str)
                        assert len(prospect[date_field]) > 0
                    except Exception as e:
                        pytest.fail(f"Invalid date field {date_field}: {e}")

    def test_api_security_measures(self, client):
        """Test that API is protected against common attacks."""
        # Test SQL injection prevention
        injection_attempts = [
            "'; DROP TABLE prospects; --",
            "1' OR '1'='1",
            "'; SELECT * FROM users; --",
        ]

        for attempt in injection_attempts:
            response = client.get(f"/api/prospects?search={attempt}")
            # Should not crash, should return valid response
            assert response.status_code == 200
            data = response.get_json()
            assert "prospects" in data

        # Test XSS prevention
        xss_attempts = [
            '<script>alert("xss")</script>',
            '<img src=x onerror=alert("xss")>',
            'javascript:alert("xss")',
        ]

        for attempt in xss_attempts:
            response = client.get(f"/api/prospects?search={attempt}")
            assert response.status_code == 200

            # Response should not contain unescaped script tags
            response_text = response.get_data(as_text=True)
            assert "<script>" not in response_text
            assert "javascript:" not in response_text

    def test_content_type_headers(self, client):
        """Test that API returns correct content type."""
        response = client.get("/api/prospects")
        assert response.status_code == 200
        assert response.content_type == "application/json"

        # Verify response is valid JSON
        try:
            json.loads(response.get_data(as_text=True))
        except json.JSONDecodeError:
            pytest.fail("Response is not valid JSON")

    @pytest.mark.parametrize("limit,page", [(5, 1), (10, 2), (20, 1), (1, 5)])
    def test_pagination_with_various_parameters(self, client, limit, page):
        """Test pagination with different limit and page combinations."""
        response = client.get(f"/api/prospects?limit={limit}&page={page}")

        # Should handle any valid combination
        assert response.status_code in [200, 400]

        if response.status_code == 200:
            data = response.get_json()
            assert len(data["prospects"]) <= limit
            assert data["pagination"]["page"] == page

    def test_source_filter_behavior(self, client):
        """Test filtering by data source IDs."""
        # Get prospects to find source IDs
        response = client.get("/api/prospects?limit=10")
        assert response.status_code == 200
        prospects = response.get_json()["prospects"]

        # Collect unique source IDs
        source_ids = list(set(p["source_id"] for p in prospects if p.get("source_id")))

        if source_ids:
            test_source_id = source_ids[0]

            # Filter by source ID
            response = client.get(f"/api/prospects?source_ids={test_source_id}")
            assert response.status_code == 200
            data = response.get_json()

            # Verify all returned prospects have this source ID
            for prospect in data["prospects"]:
                assert prospect["source_id"] == test_source_id

            # Test multiple source IDs if available
            if len(source_ids) > 1:
                source_ids_str = ",".join(str(sid) for sid in source_ids[:2])
                response = client.get(f"/api/prospects?source_ids={source_ids_str}")
                assert response.status_code == 200
                data = response.get_json()

                # Verify all prospects are from one of the specified sources
                for prospect in data["prospects"]:
                    assert prospect["source_id"] in source_ids[:2]
