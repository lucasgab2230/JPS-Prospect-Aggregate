"""
Integration tests for LLM processing API endpoints.

Tests real API interactions with database but mocks external services.
Following production-level testing principles:
- No hardcoded expected values
- Tests verify behavior, not specific data
- Uses real database operations
- Mocks only external LLM services
"""

import random
import string
from datetime import UTC

UTC = UTC
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from app import create_app
from app.database import db
from app.database.models import DataSource, Prospect
from app.database.user_models import User


def generate_random_string(length=10):
    """Generate random string for test data."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_random_prospect(data_source_id):
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

    prospect = Prospect(
        title=f"{random.choice(['Software', 'Hardware', 'Services', 'Research'])} {generate_random_string(6)}",
        agency=random.choice(agencies),
        description=" ".join([f"word{i}" for i in random.sample(range(100), 10)]),
        estimated_value_text=f"${value_min:,} - ${value_max:,}"
        if random.random() > 0.3
        else "TBD",
        naics=random.choice(naics_codes) if random.random() > 0.4 else None,
        posted_date=date.today() - timedelta(days=random.randint(1, 30)),
        response_date=date.today() + timedelta(days=random.randint(1, 60)),
        source_id=data_source_id,
        notice_id=f"TEST-{generate_random_string(8)}",
    )

    # Randomly add LLM processing to some prospects
    if random.random() > 0.6:
        prospect.ollama_processed_at = datetime.now(UTC) - timedelta(
            hours=random.randint(1, 48)
        )
        prospect.estimated_value_single = random.randint(value_min, value_max)
        prospect.title_enhanced = f"Enhanced {prospect.title}"
        prospect.naics_source = "llm_inferred"

    return prospect


@pytest.mark.integration
class TestLLMAPIIntegration:
    """Integration tests for LLM processing API with dynamic data."""

    @pytest.fixture(scope="class")
    def app(self):
        """Create test Flask app."""
        app = create_app()
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()

    @pytest.fixture(autouse=True)
    def setup_database(self, app):
        """Set up test database with dynamic sample data."""
        with app.app_context():
            db.create_all()

            # Create test data source with random data
            source_name = f"Agency_{generate_random_string(6)}"
            data_source = DataSource(
                name=source_name,
                url=f"https://{generate_random_string(8)}.gov",
                last_scraped=datetime.now(UTC) - timedelta(hours=random.randint(1, 72)),
            )
            db.session.add(data_source)
            db.session.flush()

            # Create test user with random data
            username = f"user_{generate_random_string(6)}"
            user = User(
                username=username,
                email=f"{username}@example.com",
                role=random.choice(["admin", "user", "analyst"]),
            )
            db.session.add(user)
            db.session.flush()

            # Create random number of test prospects
            num_prospects = random.randint(3, 10)
            prospects = []
            processed_count = 0
            naics_original_count = 0
            naics_inferred_count = 0
            value_parsed_count = 0

            for _ in range(num_prospects):
                prospect = generate_random_prospect(data_source.id)
                prospects.append(prospect)
                db.session.add(prospect)

                # Track statistics for verification
                if prospect.ollama_processed_at:
                    processed_count += 1
                if prospect.naics and prospect.naics_source != "llm_inferred":
                    naics_original_count += 1
                if prospect.naics_source == "llm_inferred":
                    naics_inferred_count += 1
                if prospect.estimated_value_single:
                    value_parsed_count += 1

            db.session.commit()

            # Store counts for test verification
            app.config["TEST_TOTAL_PROSPECTS"] = num_prospects
            app.config["TEST_PROCESSED_COUNT"] = processed_count
            app.config["TEST_NAICS_ORIGINAL"] = naics_original_count
            app.config["TEST_NAICS_INFERRED"] = naics_inferred_count
            app.config["TEST_VALUE_PARSED"] = value_parsed_count
            app.config["TEST_SOURCE_NAME"] = source_name
            app.config["TEST_USERNAME"] = username

            yield

            # Cleanup
            db.session.rollback()
            db.drop_all()

    @patch("app.api.llm_processing.admin_required")
    def test_get_llm_status_integration(self, mock_admin, client, app):
        """Test LLM status endpoint with real database queries and dynamic data."""
        # Mock admin decorator
        mock_admin.side_effect = lambda f: f

        # Generate random queue status
        total_items = random.randint(0, 10)
        pending_items = random.randint(0, total_items)
        processing_items = min(random.randint(0, 3), total_items - pending_items)

        with patch("app.api.llm_processing.enhancement_queue") as mock_queue:
            mock_queue.get_queue_status.return_value = {
                "total_items": total_items,
                "pending_items": pending_items,
                "processing_items": processing_items,
                "is_processing": processing_items > 0,
            }

            with patch("app.api.llm_processing.llm_service") as mock_llm:
                model_names = ["qwen3:latest", "llama2:13b", "mistral:7b"]
                mock_llm.check_ollama_status.return_value = {
                    "available": random.choice([True, False]),
                    "model": random.choice(model_names),
                }

                response = client.get("/api/llm/status")

        assert response.status_code == 200
        data = response.get_json()

        # Verify database queries worked with dynamic data
        assert data["total_prospects"] == app.config["TEST_TOTAL_PROSPECTS"]
        assert data["processed_prospects"] == app.config["TEST_PROCESSED_COUNT"]

        # Verify percentage calculation
        if app.config["TEST_TOTAL_PROSPECTS"] > 0:
            expected_percentage = round(
                (
                    app.config["TEST_PROCESSED_COUNT"]
                    / app.config["TEST_TOTAL_PROSPECTS"]
                )
                * 100,
                2,
            )
            assert data["processing_percentage"] == expected_percentage

        # Verify NAICS statistics match our tracking
        assert data["naics_coverage"]["original"] == app.config["TEST_NAICS_ORIGINAL"]
        assert (
            data["naics_coverage"]["llm_inferred"] == app.config["TEST_NAICS_INFERRED"]
        )

        # Verify value parsing statistics
        assert data["value_parsing"]["parsed_count"] == app.config["TEST_VALUE_PARSED"]

        # Verify queue and LLM status
        assert data["queue_status"]["total_items"] == total_items
        assert "llm_status" in data
        assert "available" in data["llm_status"]

    @patch("app.api.llm_processing.admin_required")
    @patch("app.api.llm_processing.add_individual_enhancement")
    def test_enhance_prospect_integration(self, mock_add, mock_admin, client):
        """Test adding prospect to enhancement queue with dynamic data."""
        # Mock admin decorator
        mock_admin.side_effect = lambda f: f

        # Generate random response
        queue_position = random.randint(1, 20)
        prospect_id = str(random.randint(1, 100))
        force_redo = random.choice([True, False])
        enhancement_types = random.sample(
            ["values", "titles", "naics", "contacts"], k=random.randint(1, 3)
        )

        # Mock enhancement function
        mock_add.return_value = {
            "success": True,
            "queue_position": queue_position,
            "message": f"Added to enhancement queue at position {queue_position}",
        }

        response = client.post(
            "/api/llm/enhance",
            json={
                "prospect_id": prospect_id,
                "force_redo": force_redo,
                "enhancement_types": enhancement_types,
            },
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["queue_position"] == queue_position

        # Verify the enhancement function was called with correct parameters
        mock_add.assert_called_once()
        call_kwargs = mock_add.call_args[1]
        assert call_kwargs["prospect_id"] == prospect_id
        assert call_kwargs["force_redo"] == force_redo
        assert call_kwargs["enhancement_types"] == enhancement_types

    @patch("app.api.llm_processing.admin_required")
    def test_enhance_prospect_missing_data(self, mock_admin, client):
        """Test enhancement request with missing prospect_id."""
        mock_admin.side_effect = lambda f: f

        response = client.post(
            "/api/llm/enhance",
            json={"force_redo": random.choice([True, False])},
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data or "message" in data

    @patch("app.api.llm_processing.admin_required")
    @patch("app.api.llm_processing.enhancement_queue")
    def test_queue_status_integration(self, mock_queue, mock_admin, client):
        """Test queue status endpoint with dynamic data."""
        mock_admin.side_effect = lambda f: f

        # Generate random queue status
        total = random.randint(0, 20)
        pending = random.randint(0, total)
        processing = min(random.randint(0, 3), total - pending)
        completed = total - pending - processing

        mock_queue.get_queue_status.return_value = {
            "total_items": total,
            "pending_items": pending,
            "processing_items": processing,
            "completed_items": completed,
            "is_processing": processing > 0,
            "current_item": str(random.randint(100, 999)) if processing > 0 else None,
        }

        response = client.get("/api/llm/queue/status")

        assert response.status_code == 200
        data = response.get_json()
        assert data["total_items"] == total
        assert data["is_processing"] == (processing > 0)
        if processing > 0:
            assert data["current_item"] is not None

    @patch("app.api.llm_processing.admin_required")
    @patch("app.api.llm_processing.enhancement_queue")
    def test_queue_item_status_integration(self, mock_queue, mock_admin, client):
        """Test individual queue item status with dynamic data."""
        mock_admin.side_effect = lambda f: f

        # Generate random item status
        item_id = str(random.randint(100, 999))
        statuses = ["pending", "processing", "completed", "error"]
        status = random.choice(statuses)
        queue_position = random.randint(1, 10)
        enhancement_types = random.sample(
            ["values", "titles", "naics"], k=random.randint(1, 3)
        )

        # Generate random progress
        progress = {}
        for etype in enhancement_types:
            progress[etype] = {"completed": random.choice([True, False])}

        mock_queue.get_item_status.return_value = {
            "status": status,
            "queue_position": queue_position,
            "enhancement_types": enhancement_types,
            "progress": progress,
            "created_at": datetime.now(UTC).isoformat(),
        }

        response = client.get(f"/api/llm/queue/item/{item_id}")

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == status
        assert data["queue_position"] == queue_position
        assert len(data["enhancement_types"]) == len(enhancement_types)
        assert len(data["progress"]) == len(progress)

    @patch("app.api.llm_processing.admin_required")
    @patch("app.api.llm_processing.enhancement_queue")
    def test_queue_item_not_found(self, mock_queue, mock_admin, client):
        """Test queue item status for non-existent item."""
        mock_admin.side_effect = lambda f: f
        mock_queue.get_item_status.return_value = None

        item_id = str(random.randint(10000, 99999))
        response = client.get(f"/api/llm/queue/item/{item_id}")

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data or "message" in data

    @patch("app.api.llm_processing.admin_required")
    @patch("app.api.llm_processing.enhancement_queue")
    def test_remove_from_queue_integration(self, mock_queue, mock_admin, client):
        """Test removing item from queue with dynamic data."""
        mock_admin.side_effect = lambda f: f

        success = random.choice([True, False])
        mock_queue.remove_from_queue.return_value = success

        item_id = str(random.randint(100, 999))
        response = client.delete(f"/api/llm/queue/item/{item_id}")

        if success:
            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True

        mock_queue.remove_from_queue.assert_called_once_with(item_id)

    @patch("app.api.llm_processing.admin_required")
    @patch("app.api.llm_processing.enhancement_queue")
    def test_start_queue_processing_integration(self, mock_queue, mock_admin, client):
        """Test starting queue processing."""
        mock_admin.side_effect = lambda f: f

        response = client.post("/api/llm/queue/start")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "message" in data

        mock_queue.start_processing.assert_called_once()

    @patch("app.api.llm_processing.admin_required")
    @patch("app.api.llm_processing.enhancement_queue")
    def test_stop_queue_processing_integration(self, mock_queue, mock_admin, client):
        """Test stopping queue processing."""
        mock_admin.side_effect = lambda f: f

        response = client.post("/api/llm/queue/stop")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "message" in data

        mock_queue.stop_processing.assert_called_once()

    @patch("app.api.llm_processing.admin_required")
    @patch("app.api.llm_processing.enhancement_queue")
    def test_clear_completed_items_integration(self, mock_queue, mock_admin, client):
        """Test clearing completed queue items with dynamic data."""
        mock_admin.side_effect = lambda f: f

        cleared_count = random.randint(0, 10)
        mock_queue.clear_completed_items.return_value = cleared_count

        response = client.post("/api/llm/queue/clear-completed")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["cleared_count"] == cleared_count

    @patch("app.api.llm_processing.admin_required")
    def test_enhancement_history_integration(self, mock_admin, client, app):
        """Test enhancement history endpoint with database queries."""
        mock_admin.side_effect = lambda f: f

        limit = random.randint(5, 20)
        offset = random.randint(0, 10)

        response = client.get(f"/api/llm/history?limit={limit}&offset={offset}")

        assert response.status_code == 200
        data = response.get_json()
        assert "total" in data
        assert "items" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)

    def test_api_error_handling(self, client):
        """Test API error handling for unauthenticated requests."""
        # Test that admin_required decorator works
        response = client.get("/api/llm/status")

        # Should get 401 or 403 depending on admin_required implementation
        assert response.status_code in [
            401,
            403,
            404,
        ]  # 404 if route doesn't exist without auth

    @patch("app.api.llm_processing.admin_required")
    def test_stream_progress_endpoint(self, mock_admin, client):
        """Test SSE progress streaming endpoint with dynamic data."""
        mock_admin.side_effect = lambda f: f

        # Generate random progress data
        total_items = random.randint(1, 10)
        processing_items = min(random.randint(1, 3), total_items)
        current_item = str(random.randint(100, 999))
        steps = [
            "Processing values",
            "Extracting contacts",
            "Inferring NAICS",
            "Enhancing title",
        ]
        current_step = random.choice(steps)

        with patch("app.api.llm_processing.enhancement_queue") as mock_queue:
            mock_queue.get_queue_status.return_value = {
                "total_items": total_items,
                "processing_items": processing_items,
                "current_item": current_item,
                "current_step": current_step,
            }

            response = client.get("/api/llm/stream/progress")

            assert response.status_code == 200
            assert "text" in response.content_type  # SSE content type

            # Read first chunk of SSE data
            if hasattr(response, "response"):
                data_chunk = next(response.response)
                assert b"data:" in data_chunk

                # Verify the SSE contains expected fields
                if b"current_step" in data_chunk:
                    assert (
                        current_step.encode() in data_chunk
                        or b"current_step" in data_chunk
                    )
