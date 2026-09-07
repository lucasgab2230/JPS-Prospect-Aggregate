"""
Unit tests for LLM Processing API endpoints.

Tests all endpoints in the llm_processing blueprint following production-level principles:
- No hardcoded expected values
- Tests verify behavior, not specific data
- Uses real database operations where possible
- Mocks only external services
"""

import json
import random
from datetime import UTC

UTC = UTC
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app import create_app
from app.database import db
from app.database.models import DataSource, Prospect


class TestLLMProcessingAPI:
    """Test suite for LLM processing API endpoints following black-box testing principles."""

    @pytest.fixture(scope="class")
    def app(self):
        """Create test Flask app with real database."""
        app = create_app()
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["SECRET_KEY"] = f"test-secret-{random.randint(1000, 9999)}"
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

            # Create test data sources
            num_sources = random.randint(1, 3)
            sources = []
            for i in range(num_sources):
                source = DataSource(
                    name=f"LLM Test Source {i}",
                    url=f"https://source{i}.test.gov",
                    last_scraped=datetime.now(UTC)
                    - timedelta(days=random.randint(0, 7)),
                )
                db.session.add(source)
                sources.append(source)

            db.session.flush()

            # Create test prospects with various enhancement states
            num_prospects = random.randint(10, 30)
            prospects = []

            for i in range(num_prospects):
                # Randomly assign enhancement attributes
                is_processed = random.random() > 0.3
                has_naics = random.random() > 0.4
                has_value = random.random() > 0.5
                has_title_enhanced = random.random() > 0.4
                has_set_aside = random.random() > 0.6

                prospect = Prospect(
                    id=f"LLM-TEST-{random.randint(1000, 9999)}-{i}",
                    title=f"{random.choice(['Software', 'Hardware', 'Consulting'])} Contract {i}",
                    description=f"Description for contract {i}",
                    agency=f"Agency {random.choice(['A', 'B', 'C'])}",
                    naics="541511" if has_naics and random.random() > 0.5 else None,
                    naics_source="original"
                    if has_naics and random.random() > 0.7
                    else "llm_inferred"
                    if has_naics
                    else None,
                    estimated_value_text=f"${random.randint(10, 500) * 1000:,}"
                    if random.random() > 0.3
                    else "TBD",
                    estimated_value_single=random.randint(10000, 1000000)
                    if has_value
                    else None,
                    title_enhanced=f"Enhanced Title {i}"
                    if has_title_enhanced
                    else None,
                    set_aside_standardized=random.choice(
                        ["SMALL_BUSINESS", "EIGHT_A", "WOSB", None]
                    )
                    if has_set_aside
                    else None,
                    source_id=random.choice(sources).id,
                    loaded_at=datetime.now(UTC)
                    - timedelta(hours=random.randint(0, 168)),
                    ollama_processed_at=datetime.now(UTC) if is_processed else None,
                    ollama_model_version="test-model-v1" if is_processed else None,
                    enhancement_status=random.choice(
                        ["idle", "queued", "processing", "completed", "failed"]
                    ),
                )
                db.session.add(prospect)
                prospects.append(prospect)

            db.session.commit()

            # Store test data for use in tests
            self.test_sources = sources
            self.test_prospects = prospects

            yield

            # Cleanup
            db.session.rollback()
            db.drop_all()

    def _auth_request(
        self, client, method, url, user_id=None, user_role=None, **kwargs
    ):
        """Helper method to make authenticated requests."""
        with client.session_transaction() as sess:
            sess["user_id"] = user_id or random.randint(1, 100)
            sess["user_role"] = user_role or random.choice(["user", "admin"])

        method_func = getattr(client, method)
        return method_func(url, **kwargs)

    def test_get_llm_status_behavior(self, client):
        """Test that LLM status endpoint returns correct statistics."""
        # Mock only the external LLM service check
        with patch("app.api.llm_processing.llm_service") as mock_llm:
            mock_llm.check_ollama_status.return_value = {
                "available": random.choice([True, False]),
                "model": f"model-{random.choice(['a', 'b', 'c'])}",
            }

            # Mock enhancement queue (external service)
            with patch("app.api.llm_processing.enhancement_queue") as mock_queue:
                queue_items = random.randint(0, 20)
                mock_queue.get_queue_status.return_value = {
                    "total_items": queue_items,
                    "pending_items": random.randint(0, queue_items),
                    "processing_items": random.randint(0, min(3, queue_items)),
                    "completed_items": random.randint(0, queue_items),
                    "is_processing": random.choice([True, False]),
                }

                response = self._auth_request(client, "get", "/api/llm/status")

        assert response.status_code == 200
        data = response.get_json()

        # Verify response structure (not specific values)
        assert "total_prospects" in data
        assert "processed_prospects" in data
        assert "naics_coverage" in data
        assert "value_parsing" in data
        assert "title_enhancement" in data
        assert "set_aside_standardization" in data

        # Verify data consistency
        assert data["total_prospects"] >= 0
        assert data["processed_prospects"] >= 0
        assert data["processed_prospects"] <= data["total_prospects"]

        # Verify percentages are valid
        if "total_percentage" in data.get("naics_coverage", {}):
            assert 0 <= data["naics_coverage"]["total_percentage"] <= 100

        if "total_percentage" in data.get("value_parsing", {}):
            assert 0 <= data["value_parsing"]["total_percentage"] <= 100

    def test_add_to_enhancement_queue_success(self, client):
        """Test adding a prospect to enhancement queue."""
        # Select a random prospect
        prospect = random.choice(self.test_prospects)

        # Mock the enhancement queue service
        with patch("app.api.llm_processing.add_individual_enhancement") as mock_add:
            queue_item_id = f"queue-{random.randint(1000, 9999)}"
            mock_add.return_value = {
                "queue_item_id": queue_item_id,
                "was_existing": random.choice([True, False]),
            }

            response = self._auth_request(
                client,
                "post",
                "/api/llm/enhance-single",
                json={
                    "prospect_id": prospect.id,
                    "force_redo": random.choice([True, False]),
                    "enhancement_type": random.choice(
                        ["all", "values", "titles", "naics"]
                    ),
                },
            )

        assert response.status_code == 200
        data = response.get_json()

        # Verify response structure
        assert "queue_item_id" in data
        assert data["queue_item_id"] == queue_item_id

        # Verify the service was called
        assert mock_add.called

    def test_add_to_enhancement_queue_invalid_prospect(self, client):
        """Test adding non-existent prospect to queue."""
        fake_prospect_id = f"FAKE-{random.randint(10000, 99999)}"

        response = self._auth_request(
            client,
            "post",
            "/api/llm/enhance-single",
            json={"prospect_id": fake_prospect_id},
        )

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_add_to_enhancement_queue_validation(self, client):
        """Test validation for enhancement queue endpoint."""
        # Test missing prospect_id
        response = self._auth_request(
            client, "post", "/api/llm/enhance-single", json={"force_redo": True}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

        # Test empty request
        response = self._auth_request(
            client, "post", "/api/llm/enhance-single", json={}
        )

        assert response.status_code == 400

    def test_get_queue_status(self, client):
        """Test getting enhancement queue status."""
        with patch("app.api.llm_processing.enhancement_queue") as mock_queue:
            # Generate random queue status
            total = random.randint(0, 50)
            pending = random.randint(0, total)
            processing = random.randint(0, min(5, total - pending))
            completed = total - pending - processing

            mock_queue.get_queue_status.return_value = {
                "total_items": total,
                "pending_items": pending,
                "processing_items": processing,
                "completed_items": completed,
                "is_processing": processing > 0,
                "current_item": f"item-{random.randint(1, 100)}"
                if processing > 0
                else None,
            }

            response = self._auth_request(client, "get", "/api/llm/queue/status")

        assert response.status_code == 200
        data = response.get_json()

        # Verify response structure and consistency
        assert "total_items" in data
        assert "pending_items" in data
        assert "processing_items" in data
        assert "completed_items" in data
        assert "is_processing" in data

        # Verify data consistency
        assert data["total_items"] >= 0
        assert data["pending_items"] >= 0
        assert data["processing_items"] >= 0
        assert data["completed_items"] >= 0

        # If processing, should have current item
        if data["is_processing"]:
            assert data["processing_items"] > 0

    def test_get_queue_item_status(self, client):
        """Test getting status of specific queue item."""
        item_id = f"item-{random.randint(1000, 9999)}"

        with patch("app.api.llm_processing.enhancement_queue") as mock_queue:
            # Generate random item status
            statuses = ["pending", "processing", "completed", "failed"]
            status = random.choice(statuses)

            mock_queue.get_item_status.return_value = {
                "status": status,
                "queue_position": random.randint(1, 10)
                if status == "pending"
                else None,
                "progress": {
                    "values": {"completed": random.choice([True, False])},
                    "titles": {"completed": random.choice([True, False])},
                    "naics": {"completed": random.choice([True, False])},
                }
                if status == "processing"
                else {},
                "created_at": datetime.now(UTC).isoformat(),
            }

            response = self._auth_request(
                client, "get", f"/api/llm/queue/item/{item_id}"
            )

        assert response.status_code == 200
        data = response.get_json()

        # Verify response structure
        assert "status" in data
        assert data["status"] in statuses

        # Verify status-specific fields
        if data["status"] == "pending":
            assert "queue_position" in data
            assert data["queue_position"] > 0

        if data["status"] == "processing":
            assert "progress" in data

    def test_get_queue_item_not_found(self, client):
        """Test getting status of non-existent queue item."""
        with patch("app.api.llm_processing.enhancement_queue") as mock_queue:
            mock_queue.get_item_status.return_value = None

            response = self._auth_request(
                client, "get", "/api/llm/queue/item/nonexistent"
            )

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_cancel_queue_item(self, client):
        """Test cancelling a queue item."""
        item_id = f"item-{random.randint(1000, 9999)}"

        with patch("app.api.llm_processing.enhancement_queue") as mock_queue:
            # Randomly decide if cancellation succeeds
            success = random.choice([True, False])
            mock_queue.cancel_item.return_value = success

            response = self._auth_request(
                client, "post", f"/api/llm/queue/item/{item_id}/cancel"
            )

        if success:
            assert response.status_code == 200
            data = response.get_json()
            assert "message" in data
        else:
            # Implementation may return 200 with error message or different status
            assert response.status_code in [200, 400, 404]

    def test_start_queue_worker(self, client):
        """Test starting the queue processing worker."""
        with patch("app.api.llm_processing.enhancement_queue") as mock_queue:
            response = self._auth_request(client, "post", "/api/llm/queue/start-worker")

        assert response.status_code == 200
        data = response.get_json()
        assert "message" in data

        # Verify worker was started
        mock_queue.start_worker.assert_called_once()

    def test_stop_queue_worker(self, client):
        """Test stopping the queue processing worker."""
        with patch("app.api.llm_processing.enhancement_queue") as mock_queue:
            response = self._auth_request(client, "post", "/api/llm/queue/stop-worker")

        assert response.status_code == 200
        data = response.get_json()
        assert "message" in data

        # Verify worker was stopped
        mock_queue.stop_worker.assert_called_once()

    def test_authentication_required(self, client):
        """Test that authentication is required for LLM endpoints."""
        # Test without session (no authentication)
        endpoints = [
            "/api/llm/status",
            "/api/llm/queue/status",
            "/api/llm/queue/item/123",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            # Should either redirect to login or return 401
            assert response.status_code in [401, 302]

    def test_api_response_format(self, client):
        """Test that all API responses are valid JSON."""
        with patch("app.api.llm_processing.enhancement_queue") as mock_queue:
            mock_queue.get_queue_status.return_value = {
                "total_items": 0,
                "pending_items": 0,
                "processing_items": 0,
                "completed_items": 0,
                "is_processing": False,
            }

            response = self._auth_request(client, "get", "/api/llm/queue/status")

        assert response.status_code == 200
        assert response.content_type == "application/json"

        # Verify response is valid JSON
        try:
            json.loads(response.get_data(as_text=True))
        except json.JSONDecodeError:
            pytest.fail("Response is not valid JSON")

    def test_error_handling(self, client):
        """Test that API handles errors gracefully."""
        # Test with enhancement queue service failure
        with patch("app.api.llm_processing.enhancement_queue") as mock_queue:
            mock_queue.get_queue_status.side_effect = Exception("Service error")

            response = self._auth_request(client, "get", "/api/llm/queue/status")

        # Should handle error gracefully
        assert response.status_code in [500, 503]
        data = response.get_json()
        assert "error" in data or "message" in data

    @pytest.mark.parametrize(
        "enhancement_type", ["all", "values", "titles", "naics", "set_asides"]
    )
    def test_enhancement_types(self, client, enhancement_type):
        """Test different enhancement types."""
        prospect = random.choice(self.test_prospects)

        with patch("app.api.llm_processing.add_individual_enhancement") as mock_add:
            mock_add.return_value = {
                "queue_item_id": f"queue-{enhancement_type}",
                "was_existing": False,
            }

            response = self._auth_request(
                client,
                "post",
                "/api/llm/enhance-single",
                json={"prospect_id": prospect.id, "enhancement_type": enhancement_type},
            )

        assert response.status_code == 200
        data = response.get_json()
        assert "queue_item_id" in data

        # Verify correct enhancement type was passed
        call_args = mock_add.call_args
        assert call_args[1]["enhancement_type"] == enhancement_type
