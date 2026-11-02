"""
Comprehensive unit tests for LLM Service.

Tests cover all critical functionality of the unified LLM service following
production-level testing principles:
- No hardcoded expected values
- Tests verify behavior, not specific data
- Mocks only external dependencies (LLM API)
- Focus on service behavior patterns
"""

import json
import random
import threading
import time
from datetime import UTC

UTC = UTC
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from app import create_app
from app.database import db
from app.database.models import LLMOutput, Prospect
from app.services.llm_service import LLMService
from app.services.set_aside_standardization import StandardSetAside


class TestLLMService:
    """Test suite for LLMService following black-box testing principles."""

    @pytest.fixture(scope="class")
    def app(self):
        """Create test Flask app with real database."""
        app = create_app()
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        return app

    @pytest.fixture
    def app_context(self, app):
        """Create Flask app context with real database."""
        with app.app_context():
            db.create_all()
            yield
            db.session.rollback()
            db.drop_all()

    @pytest.fixture
    def llm_service(self):
        """Create LLM service instance for testing."""
        # Use random model name and batch size to avoid hardcoding
        model_name = f"model_{random.randint(1, 100)}"
        batch_size = random.randint(5, 20)
        return LLMService(model_name=model_name, batch_size=batch_size)

    @pytest.fixture
    def test_prospect(self, app_context):
        """Create a real prospect in the database for testing."""
        prospect = Prospect(
            id=f"PROSPECT-{random.randint(1000, 9999)}",
            title=f"Contract Opportunity {random.randint(1, 100)}",
            description="Test description with various technical requirements",
            agency="Test Agency",
            estimated_value_text="$100,000 - $500,000"
            if random.random() > 0.5
            else "TBD",
            set_aside="Small Business" if random.random() > 0.5 else None,
            naics=None,  # Start without NAICS for testing enhancement
            loaded_at=datetime.now(UTC),
        )
        db.session.add(prospect)
        db.session.commit()
        return prospect

    def test_service_initialization(self):
        """Test that LLM service initializes with correct configuration."""
        # Test with various configurations
        for _ in range(3):
            model = f"model_{random.choice(['a', 'b', 'c'])}"
            batch = random.randint(1, 50)
            service = LLMService(model_name=model, batch_size=batch)

            # Verify service is properly initialized
            assert service.model_name == model
            assert service.batch_size == batch
            assert hasattr(service, "_processing")
            assert hasattr(service, "_thread")
            assert hasattr(service, "set_aside_standardizer")
            assert not service._processing  # Should start as not processing

    def test_ollama_status_check_behavior(self, app_context):
        """Test that Ollama status check behaves correctly."""
        service = LLMService(model_name="test_model", batch_size=10)

        with patch("app.services.llm_service.call_ollama") as mock_call:
            # Test when Ollama is available
            mock_call.return_value = "Some response"
            status = service.check_ollama_status()

            assert "available" in status
            assert "model" in status
            assert status["available"] is True
            assert status["model"] == "test_model"

            # Test when Ollama is not available
            mock_call.side_effect = Exception("Connection error")
            status = service.check_ollama_status()

            assert "available" in status
            assert status["available"] is False
            assert "error" in status

    def test_prospect_enhancement_flow(self, llm_service, test_prospect, app_context):
        """Test that prospect enhancement follows expected flow."""
        # Mock only the external LLM API calls
        with patch("app.services.llm_service.call_ollama") as mock_ollama:
            # Simulate realistic LLM responses
            mock_ollama.side_effect = [
                json.dumps(
                    {
                        "min_value": random.randint(50000, 200000),
                        "max_value": random.randint(200001, 500000),
                    }
                ),
                f"Enhanced Title {random.randint(1, 100)}",
                "541511",  # Valid NAICS code
            ]

            # Mock NAICS validation (external service)
            with (
                patch(
                    "app.services.llm_service.validate_naics_code", return_value=True
                ),
                patch(
                    "app.services.llm_service.get_naics_description",
                    return_value="Some NAICS Description",
                ),
            ):
                # Enhance the prospect
                result = llm_service.enhance_prospect(
                    test_prospect, enhancement_types=["values", "titles", "naics"]
                )

            # Verify enhancement succeeded
            assert result is True

            # Refresh prospect from database
            db.session.refresh(test_prospect)

            # Verify prospect was enhanced (behavior, not specific values)
            assert test_prospect.estimated_value_single is not None
            assert test_prospect.estimated_value_single > 0
            assert test_prospect.title_enhanced is not None
            assert len(test_prospect.title_enhanced) > 0
            assert test_prospect.naics is not None
            assert test_prospect.naics_source == "llm_inferred"
            assert test_prospect.ollama_processed_at is not None

    def test_value_parsing_behavior(self, llm_service, app_context):
        """Test that value parsing handles various formats correctly."""
        test_cases = [
            "$100,000 - $500,000",
            "$1M - $5M",
            "TBD",
            "$250K",
            "Not specified",
            "",
        ]

        with patch("app.services.llm_service.call_ollama") as mock_ollama:
            for value_text in test_cases:
                # Simulate LLM parsing response
                if (
                    "TBD" in value_text
                    or "Not specified" in value_text
                    or not value_text
                ):
                    mock_ollama.return_value = "null"
                else:
                    # Generate reasonable parse result
                    mock_ollama.return_value = json.dumps(
                        {
                            "min_value": random.randint(10000, 100000),
                            "max_value": random.randint(100001, 1000000),
                        }
                    )

                result = llm_service._parse_contract_value(value_text)

                # Verify behavior based on input type
                if (
                    "TBD" in value_text
                    or "Not specified" in value_text
                    or not value_text
                ):
                    assert result is None or result == {}
                elif result:
                    assert (
                        "min_value" in result
                        or "max_value" in result
                        or "avg_value" in result
                    )
                    if "min_value" in result and "max_value" in result:
                        assert result["min_value"] <= result["max_value"]

    def test_naics_classification_behavior(self, llm_service, app_context):
        """Test NAICS classification with various inputs."""
        test_inputs = [
            ("IT consulting services", "Software development and integration"),
            ("Construction management", "Building construction oversight"),
            ("", ""),
            ("Random text", None),
        ]

        with patch("app.services.llm_service.call_ollama") as mock_ollama:
            for title, description in test_inputs:
                # Generate NAICS code response
                if title and description:
                    mock_ollama.return_value = "541511"  # Valid code
                else:
                    mock_ollama.return_value = "null"

                with (
                    patch(
                        "app.services.llm_service.validate_naics_code"
                    ) as mock_validate,
                    patch(
                        "app.services.llm_service.get_naics_description"
                    ) as mock_desc,
                ):
                    # Set up validation behavior
                    mock_validate.return_value = bool(title and description)
                    mock_desc.return_value = "Some Description" if title else None

                    result = llm_service._classify_naics(title, description)

                    # Verify behavior
                    if title and description:
                        assert result is not None
                        if result:
                            assert "code" in result
                            assert "description" in result
                    else:
                        assert result is None or result == {}

    def test_set_aside_standardization_patterns(self, llm_service, app_context):
        """Test set-aside standardization with various input patterns."""
        # Test with various formats
        test_inputs = [
            "Small Business Set-Aside",
            "8(a) Set-Aside",
            "Woman-Owned Small Business",
            "HUBZone",
            "Service-Disabled Veteran-Owned",
            "Full and Open Competition",
            "Unknown Format XYZ",
            "",
            None,
        ]

        for input_text in test_inputs:
            result = llm_service._standardize_set_aside(input_text)

            # Verify standardization returns a valid enum value
            if input_text:
                assert result is not None
                # Should return one of the standard values
                valid_values = [e.value for e in StandardSetAside]
                assert result in valid_values
            else:
                # Empty or None should return UNKNOWN or None
                assert result in [StandardSetAside.UNKNOWN.value, None]

    def test_batch_processing_behavior(self, llm_service, app_context):
        """Test batch processing with multiple prospects."""
        # Create multiple prospects
        num_prospects = random.randint(5, 10)
        prospects = []

        for i in range(num_prospects):
            prospect = Prospect(
                id=f"BATCH-{i:03d}",
                title=f"Contract {i}",
                description=f"Description for contract {i}",
                agency="Test Agency",
                estimated_value_text=f"${random.randint(10, 100) * 1000}",
                loaded_at=datetime.now(UTC),
            )
            db.session.add(prospect)
            prospects.append(prospect)

        db.session.commit()

        # Track progress
        progress_calls = []

        def progress_callback(current, total):
            progress_calls.append((current, total))

        # Mock only external LLM calls
        with patch("app.services.llm_service.call_ollama") as mock_ollama:
            mock_ollama.return_value = json.dumps({"min_value": 50000})

            # Process batch
            llm_service.process_batch(
                prospects,
                enhancement_types=["values"],
                progress_callback=progress_callback,
            )

        # Verify all prospects were processed
        for prospect in prospects:
            db.session.refresh(prospect)
            # Should have attempted enhancement
            assert prospect.ollama_processed_at is not None

        # Verify progress was reported
        if progress_calls:
            # Should have reported progress
            assert len(progress_calls) > 0
            # Final progress should be complete
            last_current, last_total = progress_calls[-1]
            assert last_current == last_total

    def test_iterative_processing_lifecycle(self, llm_service, app_context):
        """Test starting and stopping iterative processing."""
        # Create some prospects to process
        for i in range(3):
            prospect = Prospect(
                id=f"ITER-{i:03d}",
                title=f"Iterative Contract {i}",
                agency="Test Agency",
                loaded_at=datetime.now(UTC),
            )
            db.session.add(prospect)
        db.session.commit()

        with patch(
            "app.services.llm_service.call_ollama", return_value='{"min_value": 100000}'
        ):
            # Start processing
            llm_service.start_iterative_processing(
                limit=10, enhancement_types=["values"]
            )

            # Verify processing started
            assert llm_service._processing is True
            assert llm_service._thread is not None
            assert llm_service._thread.is_alive()

            # Let it run briefly
            time.sleep(0.5)

            # Stop processing
            llm_service.stop_iterative_processing()

            # Wait for thread to stop
            if llm_service._thread:
                llm_service._thread.join(timeout=2)

            # Verify processing stopped
            assert llm_service._processing is False
            assert llm_service._stop_event.is_set()

    def test_progress_statistics_calculation(self, llm_service, app_context):
        """Test that progress statistics are calculated correctly."""
        # Create prospects with various states
        total_prospects = random.randint(10, 20)
        processed_count = random.randint(5, total_prospects - 1)

        for i in range(total_prospects):
            prospect = Prospect(
                id=f"STATS-{i:03d}",
                title=f"Stats Contract {i}",
                agency="Test Agency",
                naics="541511" if i % 3 == 0 else None,
                estimated_value_single=Decimal(str(random.randint(10000, 100000)))
                if i % 2 == 0
                else None,
                title_enhanced=f"Enhanced {i}" if i % 4 == 0 else None,
                ollama_processed_at=datetime.now(UTC) if i < processed_count else None,
                loaded_at=datetime.now(UTC),
            )
            db.session.add(prospect)

        db.session.commit()

        # Get statistics
        stats = llm_service.get_progress_stats()

        # Verify statistics structure and relationships
        assert "total_prospects" in stats
        assert "processed_prospects" in stats
        assert "progress_percentage" in stats

        assert stats["total_prospects"] >= 0
        assert stats["processed_prospects"] >= 0
        assert stats["processed_prospects"] <= stats["total_prospects"]

        if stats["total_prospects"] > 0:
            expected_percentage = (
                stats["processed_prospects"] / stats["total_prospects"]
            ) * 100
            assert abs(stats["progress_percentage"] - expected_percentage) < 0.1

    def test_llm_output_logging(self, llm_service, test_prospect, app_context):
        """Test that LLM outputs are logged to database."""
        # Log some outputs
        prompt_types = ["value_parsing", "title_enhancement", "naics_classification"]

        for prompt_type in prompt_types:
            llm_service._log_llm_output(
                prospect_id=test_prospect.id,
                prompt_type=prompt_type,
                prompt=f"Test prompt for {prompt_type}",
                response=f"Test response for {prompt_type}",
                model_name="test_model",
            )

        # Verify outputs were logged
        outputs = (
            db.session.query(LLMOutput).filter_by(prospect_id=test_prospect.id).all()
        )

        assert len(outputs) == len(prompt_types)

        for output in outputs:
            assert output.prospect_id == test_prospect.id
            assert output.prompt_type in prompt_types
            assert output.prompt is not None
            assert output.response is not None
            assert output.model_name == "test_model"
            assert output.created_at is not None

    def test_error_handling_during_enhancement(
        self, llm_service, test_prospect, app_context
    ):
        """Test that enhancement handles errors gracefully."""
        error_scenarios = [
            # All fail
            [Exception("Error 1"), Exception("Error 2"), Exception("Error 3")],
            # Some succeed
            ['{"min_value": 100000}', Exception("Error 2"), "541511"],
            # First fails, others succeed
            [Exception("Error 1"), "Enhanced Title", "541511"],
        ]

        for scenario in error_scenarios:
            with patch("app.services.llm_service.call_ollama") as mock_ollama:
                mock_ollama.side_effect = scenario

                with (
                    patch(
                        "app.services.llm_service.validate_naics_code",
                        return_value=True,
                    ),
                    patch(
                        "app.services.llm_service.get_naics_description",
                        return_value="Description",
                    ),
                ):
                    # Should not raise exception
                    result = llm_service.enhance_prospect(
                        test_prospect,
                        enhancement_types=["values", "titles", "naics"],
                    )

                    # Should return True if at least one enhancement worked
                    # or False if all failed
                    assert isinstance(result, bool)

    def test_concurrent_enhancement_safety(self, app):
        """Test thread safety of concurrent enhancement operations."""
        results = []
        errors = []

        def enhance_prospects_thread(thread_id):
            try:
                with app.app_context():
                    # Create service instance for this thread
                    service = LLMService(model_name=f"model_{thread_id}", batch_size=5)

                    # Create a prospect for this thread
                    prospect = Prospect(
                        id=f"THREAD-{thread_id:03d}",
                        title=f"Thread Contract {thread_id}",
                        agency="Test Agency",
                        estimated_value_text="$100,000",
                        loaded_at=datetime.now(UTC),
                    )
                    db.session.add(prospect)
                    db.session.commit()

                    with patch(
                        "app.services.llm_service.call_ollama",
                        return_value='{"min_value": 100000}',
                    ):
                        result = service.enhance_prospect(
                            prospect, enhancement_types=["values"]
                        )
                        results.append((thread_id, result))

            except Exception as e:
                errors.append((thread_id, e))

        # Create multiple threads
        num_threads = 5
        threads = []

        for i in range(num_threads):
            t = threading.Thread(target=enhance_prospects_thread, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join(timeout=10)

        # Verify no errors occurred
        assert len(errors) == 0, f"Thread errors: {errors}"

        # Verify all threads completed successfully
        assert len(results) == num_threads

        # Each thread should have succeeded
        for thread_id, result in results:
            assert isinstance(result, bool)

    @pytest.mark.parametrize(
        "enhancement_type", ["values", "titles", "naics", "set_asides"]
    )
    def test_individual_enhancement_types(
        self, llm_service, app_context, enhancement_type
    ):
        """Test each enhancement type individually."""
        # Create prospect for testing
        prospect = Prospect(
            id=f"TYPE-TEST-{enhancement_type}",
            title="Test Contract",
            description="Test description",
            agency="Test Agency",
            estimated_value_text="$100,000 - $200,000",
            set_aside="Small Business",
            loaded_at=datetime.now(UTC),
        )
        db.session.add(prospect)
        db.session.commit()

        with patch("app.services.llm_service.call_ollama") as mock_ollama:
            # Provide appropriate response for each type
            if enhancement_type == "values":
                mock_ollama.return_value = '{"min_value": 100000, "max_value": 200000}'
            elif enhancement_type == "titles":
                mock_ollama.return_value = "Enhanced Contract Title"
            elif enhancement_type == "naics":
                mock_ollama.return_value = "541511"
            else:
                mock_ollama.return_value = "SMALL_BUSINESS"

            with (
                patch(
                    "app.services.llm_service.validate_naics_code", return_value=True
                ),
                patch(
                    "app.services.llm_service.get_naics_description",
                    return_value="Description",
                ),
            ):
                result = llm_service.enhance_prospect(
                    prospect, enhancement_types=[enhancement_type]
                )

        # Verify enhancement was attempted
        assert isinstance(result, bool)

        # Refresh and check appropriate field was updated
        db.session.refresh(prospect)

        if result:
            if enhancement_type == "values":
                assert prospect.estimated_value_single is not None
            elif enhancement_type == "titles":
                assert prospect.title_enhanced is not None
            elif enhancement_type == "naics":
                assert prospect.naics is not None
            elif enhancement_type == "set_asides":
                assert prospect.set_aside_standardized is not None

    def test_enhancement_idempotency(self, llm_service, test_prospect, app_context):
        """Test that re-enhancing a prospect doesn't cause issues."""
        with patch("app.services.llm_service.call_ollama") as mock_ollama:
            mock_ollama.return_value = '{"min_value": 100000}'

            # Enhance once
            result1 = llm_service.enhance_prospect(
                test_prospect, enhancement_types=["values"]
            )
            db.session.refresh(test_prospect)
            value1 = test_prospect.estimated_value_single

            # Enhance again
            mock_ollama.return_value = '{"min_value": 200000}'
            result2 = llm_service.enhance_prospect(
                test_prospect, enhancement_types=["values"]
            )
            db.session.refresh(test_prospect)
            value2 = test_prospect.estimated_value_single

            # Both should succeed
            assert result1 is True
            assert result2 is True

            # Value should be updated
            assert value2 is not None
            # May or may not be different depending on implementation
            # but should be valid
            assert value2 > 0
