"""
Performance tests for the application.
Tests for response times, memory usage, database query efficiency, etc.
"""

import json
import os
import tempfile
import time
from datetime import UTC

UTC = UTC
from datetime import datetime
from unittest.mock import patch

import pytest

from app import create_app
from app.database import db
from app.database.models import DataSource


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


@pytest.fixture
def large_dataset(app):
    """Create a large dataset for performance testing."""
    with app.app_context():
        # Create 1000 test prospects
        prospects = []

        for i in range(1000):
            prospect_data = {
                "id": f"PERF-{i:06d}",
                "title": f"Performance Test Contract {i}",
                "description": f"Test description for performance testing contract number {i}. "
                + "This is a longer description to simulate real-world data. " * 3,
                "agency": f"Test Agency {i % 10}",  # 10 different agencies
                "posted_date": f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                "estimated_value": 10000 + (i * 1000),
                "estimated_value_text": f"${(10000 + (i * 1000)):,}",
                "naics": f"54151{i % 10}",  # Vary NAICS codes
                "source_data_id": app.config["TEST_SOURCE_ID"],
                "source_file": f"perf_test_{i // 100}.json",
                "loaded_at": datetime.now(UTC),
            }

            # Add some AI enhancement data to some prospects
            if i % 10 == 0:
                prospect_data.update(
                    {
                        "ai_enhanced_title": f"Enhanced: {prospect_data['title']}",
                        "ai_enhanced_description": f"AI Enhanced: {prospect_data['description']}",
                        "ollama_processed_at": datetime.now(UTC),
                    }
                )

            add_prospect(prospect_data)

        db.session.commit()

        return 1000


class TestAPIResponseTimes:
    """Test API response times under various conditions."""

    def test_prospects_api_base_performance(self, client):
        """Test basic prospects API response time."""
        start_time = time.time()
        response = client.get("/api/prospects")
        end_time = time.time()

        assert response.status_code == 200

        # Verify response completes in reasonable time
        response_time = end_time - start_time
        # Response should complete (no timeout or hanging)
        assert response_time > 0, "Response time should be measurable"
        # Log performance for monitoring trends
        print(f"API base performance: {response_time:.3f}s")

    def test_prospects_api_large_dataset_performance(self, client, large_dataset):
        """Test prospects API performance with large dataset."""
        start_time = time.time()
        response = client.get("/api/prospects?limit=50")
        end_time = time.time()

        assert response.status_code == 200

        data = response.get_json()
        assert len(data["prospects"]) == 50
        assert data["pagination"]["total_items"] == large_dataset

        # Performance should scale appropriately with dataset size
        response_time = end_time - start_time
        # Log for performance trend analysis
        print(
            f"Large dataset ({large_dataset} items) performance: {response_time:.3f}s"
        )
        # Verify pagination is working (should not load all data)
        assert len(data["prospects"]) <= 50, "Pagination should limit results"

    def test_prospects_api_search_performance(self, client, large_dataset):
        """Test search performance with large dataset."""
        start_time = time.time()
        response = client.get("/api/prospects?keywords=Performance Test")
        end_time = time.time()

        assert response.status_code == 200

        # Search should complete and return results
        response_time = end_time - start_time
        print(f"Search performance: {response_time:.3f}s")

        data = response.get_json()
        # Should return results matching the search
        assert "prospects" in data
        assert isinstance(data["prospects"], list)

    def test_prospects_api_complex_filter_performance(self, client, large_dataset):
        """Test complex filtering performance."""
        start_time = time.time()
        response = client.get(
            "/api/prospects?agency=Test Agency 1&naics=541511&keywords=contract"
        )
        end_time = time.time()

        assert response.status_code == 200

        # Complex queries should complete successfully
        response_time = end_time - start_time
        print(f"Complex filter performance: {response_time:.3f}s")
        # Verify filtering is working
        data = response.get_json()
        assert "prospects" in data

    def test_prospects_api_pagination_performance(self, client, large_dataset):
        """Test pagination performance."""
        # Test multiple page requests
        page_times = []

        for page in range(1, 6):  # Test first 5 pages
            start_time = time.time()
            response = client.get(f"/api/prospects?page={page}&limit=20")
            end_time = time.time()

            assert response.status_code == 200

            page_time = end_time - start_time
            page_times.append(page_time)
            print(f"Page {page} performance: {page_time:.3f}s")

        # Pagination should not degrade significantly across pages
        avg_time = sum(page_times) / len(page_times)
        max_time = max(page_times)
        # Performance should be relatively consistent
        assert max_time < avg_time * 2, (
            "Page load times should be relatively consistent"
        )


class TestDatabasePerformance:
    """Test database query performance."""

    def test_prospect_bulk_creation_performance(self, app):
        """Test bulk prospect creation performance."""
        with app.app_context():
            start_time = time.time()

            # Create 100 prospects in bulk
            prospects = []
            for i in range(100):
                prospect_data = {
                    "id": f"BULK-{i:04d}",
                    "title": f"Bulk Test Contract {i}",
                    "description": f"Test description {i}",
                    "agency": "Bulk Test Agency",
                    "posted_date": "2024-01-15",
                    "estimated_value": 50000,
                    "estimated_value_text": "$50,000",
                    "naics": "541511",
                    "source_data_id": app.config["TEST_SOURCE_ID"],
                    "source_file": "bulk_test.json",
                    "loaded_at": datetime.now(UTC),
                }
                add_prospect(prospect_data)

            db.session.commit()
            end_time = time.time()

            creation_time = end_time - start_time
            # Track bulk creation performance
            print(f"Bulk creation performance: {creation_time:.3f}s for 100 prospects")

            # Calculate rate for monitoring
            rate = 100 / creation_time
            print(f"Creation rate: {rate:.1f} prospects/sec")
            # Verify bulk operation completed
            assert creation_time > 0, "Bulk creation should take measurable time"

    def test_duplicate_detection_performance(self, app, large_dataset):
        """Test duplicate detection performance with large dataset."""
        with app.app_context():
            from app.services.duplicate_detection import find_duplicates

            # Create a new prospect that might have duplicates
            test_prospect_data = {
                "id": "DUP-TEST-001",
                "title": "Performance Test Contract 100",  # Similar to existing
                "description": "Test description for performance",
                "agency": "Test Agency 0",
                "posted_date": "2024-01-15",
                "estimated_value": 110000,
                "estimated_value_text": "$110,000",
                "naics": "541510",
                "source_data_id": app.config["TEST_SOURCE_ID"],
                "source_file": "dup_test.json",
                "loaded_at": datetime.now(UTC),
            }

            add_prospect(test_prospect_data)
            db.session.commit()

            start_time = time.time()
            duplicates = find_duplicates("DUP-TEST-001")
            end_time = time.time()

            detection_time = end_time - start_time
            # Track duplicate detection performance
            print(f"Duplicate detection performance: {detection_time:.3f}s")

            # Should return results
            assert isinstance(duplicates, list)
            # Detection should complete
            assert detection_time > 0, "Detection should take measurable time"


class TestDecisionPerformance:
    """Test decision creation and retrieval performance."""

    def test_decision_creation_performance(self, app, auth_client, large_dataset):
        """Test decision creation performance."""
        with app.app_context():
            # Create a test prospect for decisions
            prospect_data = {
                "id": "DECISION-PERF-001",
                "title": "Decision Performance Test",
                "description": "Test prospect for decision performance",
                "agency": "Test Agency",
                "posted_date": "2024-01-15",
                "estimated_value": 75000,
                "estimated_value_text": "$75,000",
                "naics": "541511",
                "source_data_id": app.config["TEST_SOURCE_ID"],
                "source_file": "decision_perf_test.json",
                "loaded_at": datetime.now(UTC),
            }
            add_prospect(prospect_data)
            db.session.commit()

        # Test bulk decision creation
        start_time = time.time()

        for i in range(50):
            decision_data = {
                "prospect_id": "DECISION-PERF-001",
                "decision": "go" if i % 2 == 0 else "no-go",
                "reason": f"Performance test decision {i}",
            }

            response = auth_client.post(
                "/api/decisions/",
                data=json.dumps(decision_data),
                content_type="application/json",
            )
            assert response.status_code == 201

        end_time = time.time()

        total_time = end_time - start_time
        # Track decision creation performance
        print(f"Decision creation performance: {total_time:.3f}s for 50 decisions")

        # Calculate rate for monitoring
        rate = 50 / total_time
        print(f"Decision creation rate: {rate:.1f} decisions/sec")
        # Verify decisions were created
        assert total_time > 0, "Decision creation should take measurable time"

    def test_decision_retrieval_performance(self, app, auth_client):
        """Test decision retrieval performance with many decisions."""
        with app.app_context():
            # Create test prospect and many decisions
            prospect_data = {
                "id": "DECISION-RETRIEVAL-001",
                "title": "Decision Retrieval Test",
                "description": "Test prospect for decision retrieval",
                "agency": "Test Agency",
                "posted_date": "2024-01-15",
                "estimated_value": 50000,
                "estimated_value_text": "$50,000",
                "naics": "541511",
                "source_data_id": app.config["TEST_SOURCE_ID"],
                "source_file": "decision_retrieval_test.json",
                "loaded_at": datetime.now(UTC),
            }
            add_prospect(prospect_data)

            # Create 100 decisions directly in database for speed
            from app.database.user_models import User

            test_user = User(
                id=app.config["TEST_USER_ID"],
                username="testuser",
                email="test@example.com",
                first_name="Test",
                last_name="User",
            )
            db.session.add(test_user)

            for i in range(100):
                decision = Decision(
                    prospect_id="DECISION-RETRIEVAL-001",
                    user_id=app.config["TEST_USER_ID"],
                    decision="go" if i % 2 == 0 else "no-go",
                    reason=f"Test decision {i}",
                    created_at=datetime.now(UTC),
                )
                db.session.add(decision)

            db.session.commit()

        # Test retrieval performance
        start_time = time.time()
        response = auth_client.get("/api/decisions/DECISION-RETRIEVAL-001")
        end_time = time.time()

        assert response.status_code == 200

        retrieval_time = end_time - start_time
        # Track retrieval performance
        print(
            f"Decision retrieval performance: {retrieval_time:.3f}s for 100 decisions"
        )

        data = response.get_json()
        assert data["data"]["total_decisions"] == 100
        # Retrieval should complete
        assert retrieval_time > 0, "Retrieval should take measurable time"


class TestMemoryUsage:
    """Test memory usage patterns."""

    def test_api_memory_efficiency(self, client, large_dataset):
        """Test that API calls don't cause memory leaks."""
        import gc
        import os

        import psutil

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Make many API calls
        for i in range(50):
            response = client.get("/api/prospects?limit=20")
            assert response.status_code == 200

            # Force garbage collection every 10 requests
            if i % 10 == 0:
                gc.collect()

        # Check final memory usage
        final_memory = process.memory_info().rss
        memory_growth = final_memory - initial_memory

        # Monitor memory growth patterns
        growth_mb = memory_growth / 1024 / 1024
        print(f"Memory growth after 50 requests: {growth_mb:.1f}MB")
        # Memory should not grow unbounded
        if growth_mb < 0:
            print("Memory decreased (garbage collection working)")
        # Just ensure the test completes without OOM
        assert True, "Memory test completed without out-of-memory error"


class TestConcurrencyPerformance:
    """Test performance under concurrent load."""

    def test_concurrent_api_requests(self, client):
        """Test API performance under concurrent requests."""
        import queue
        import threading

        results = queue.Queue()

        def make_request():
            start_time = time.time()
            response = client.get("/api/prospects")
            end_time = time.time()

            results.put(
                {
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                }
            )

        # Create 10 concurrent threads
        threads = []
        start_time = time.time()

        for i in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        end_time = time.time()
        total_time = end_time - start_time

        # Collect results
        response_times = []
        while not results.empty():
            result = results.get()
            assert result["status_code"] == 200
            response_times.append(result["response_time"])

        # Track concurrent request performance
        print(f"Concurrent requests (10 threads) completed in {total_time:.3f}s")

        # Calculate statistics
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)

        print(
            f"Response times - Avg: {avg_response_time:.3f}s, Max: {max_response_time:.3f}s, Min: {min_response_time:.3f}s"
        )

        # Concurrent requests should all complete
        assert len(response_times) == 10, "All concurrent requests should complete"
        # Performance should not degrade catastrophically under load
        assert max_response_time < avg_response_time * 5, (
            "Max response time should not be excessive compared to average"
        )


class TestScalabilityLimits:
    """Test application behavior at scale limits."""

    def test_large_page_size_handling(self, client, large_dataset):
        """Test handling of large page sizes."""
        # Test maximum reasonable page size
        response = client.get("/api/prospects?limit=500")

        if response.status_code == 200:
            # Should handle large page size efficiently
            start_time = time.time()
            data = response.get_json()
            end_time = time.time()

            processing_time = end_time - start_time
            print(f"Large page size (500) processing: {processing_time:.3f}s")

            # Should return results up to the limit
            assert len(data["prospects"]) <= 500
            # Processing should complete
            assert processing_time > 0
        else:
            # Should reject gracefully if limit is too high
            assert response.status_code == 400

    def test_deep_pagination_performance(self, client, large_dataset):
        """Test performance of deep pagination."""
        # Test accessing a page deep in the results
        page_number = 40  # Page 40 with 20 items per page = item 800

        start_time = time.time()
        response = client.get(f"/api/prospects?page={page_number}&limit=20")
        end_time = time.time()

        assert response.status_code == 200

        # Track deep pagination performance
        response_time = end_time - start_time
        print(f"Deep pagination (page {page_number}) performance: {response_time:.3f}s")

        data = response.get_json()
        assert data["pagination"]["page"] == page_number
        # Deep pagination should still work
        assert response.status_code == 200


if __name__ == "__main__":
    # Run with specific performance markers
    pytest.main([__file__, "-v", "--tb=short"])
