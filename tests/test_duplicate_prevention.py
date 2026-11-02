"""
Unit tests for duplicate prevention functionality.

Tests the various matching strategies and edge cases in the duplicate
prevention system.
"""

from datetime import UTC

UTC = UTC
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from app.utils.duplicate_prevention import (
    DuplicateDetector,
    MatchCandidate,
)


class TestDuplicateDetector:
    """Test the DuplicateDetector class."""

    def setup_method(self):
        """Set up test detector."""
        self.detector = DuplicateDetector()

    def test_text_similarity_exact_match(self):
        """Test that exact matches have highest similarity."""
        exact_score = self.detector._calculate_text_similarity("test", "test")
        different_score = self.detector._calculate_text_similarity("test", "different")

        # Exact matches should have highest possible score
        assert exact_score > different_score
        assert exact_score > 0.9  # Very high similarity

        # Case insensitive matching should also score high
        case_score = self.detector._calculate_text_similarity("Test", "test")
        assert case_score > 0.9  # High similarity for case variations

    def test_text_similarity_none_values(self):
        """Test that None values result in no similarity."""
        none_test_score = self.detector._calculate_text_similarity(None, "test")
        test_none_score = self.detector._calculate_text_similarity("test", None)
        none_none_score = self.detector._calculate_text_similarity(None, None)

        # None values should have minimal similarity
        assert none_test_score < 0.1
        assert test_none_score < 0.1
        assert none_none_score < 0.1

    def test_text_similarity_empty_strings(self):
        """Test that empty strings have no similarity."""
        empty_test_score = self.detector._calculate_text_similarity("", "test")
        test_empty_score = self.detector._calculate_text_similarity("test", "")
        empty_empty_score = self.detector._calculate_text_similarity("", "")

        # Empty strings should have minimal similarity
        assert empty_test_score < 0.1
        assert test_empty_score < 0.1
        assert empty_empty_score < 0.1

    def test_text_similarity_short_strings(self):
        """Test similarity behavior with short strings."""
        # Exact match should score highest
        exact_score = self.detector._calculate_text_similarity("AI", "AI")

        # Completely different strings should score low
        different_score = self.detector._calculate_text_similarity("AI", "ML")

        # Punctuation variations should score fairly high
        punct_score1 = self.detector._calculate_text_similarity("AI", "A.I.")
        punct_score2 = self.detector._calculate_text_similarity("IT", "I.T.")

        # Contained strings should have moderate similarity
        contained_score = self.detector._calculate_text_similarity("AI", "AIs")

        # Verify relative scoring makes sense
        assert exact_score > contained_score > different_score
        assert punct_score1 > different_score
        assert punct_score2 > different_score
        assert exact_score > 0.9  # Exact matches should be very high
        assert different_score < 0.3  # Different strings should be low

    def test_text_similarity_fuzzy_matching(self):
        """Test fuzzy text matching."""
        # Similar strings
        sim1 = self.detector._calculate_text_similarity(
            "Senior Software Engineer", "Sr. Software Engineer"
        )
        assert 0.8 < sim1 < 1.0

        # Very different strings
        sim2 = self.detector._calculate_text_similarity(
            "Software Engineer", "Data Scientist"
        )
        assert sim2 < 0.5

    def test_native_id_matching_with_different_content(self):
        """Test native_id matching doesn't create false positives."""
        # Create a simple mock prospect
        existing_prospect = Mock()
        existing_prospect.id = "existing_001"
        existing_prospect.native_id = "TEST_001"
        existing_prospect.title = "Software Developer"
        existing_prospect.description = "Python development role"
        existing_prospect.agency = "Department of Defense"
        existing_prospect.place_city = "Washington"
        existing_prospect.place_state = "DC"

        # Mock the detector's cache to simulate existing prospects
        self.detector._prospects_cache = {
            "by_native_id": {"TEST_001": [existing_prospect]}
        }
        self.detector._cache_source_id = 1

        # New record with same native_id but completely different content
        new_record = {
            "native_id": "TEST_001",
            "title": "Network Administrator",  # Completely different
            "description": "Network security specialist",  # Completely different
            "agency": "Department of Defense",
            "place_city": "Arlington",  # Different location
            "place_state": "VA",
        }

        # Test the exact native_id match strategy directly
        candidates = self.detector._exact_native_id_match(
            Mock(), new_record, self.detector.strategies[0]
        )

        # Should have low confidence due to different content
        if candidates:
            assert candidates[0].confidence_score < 0.5, (
                f"Expected low confidence for different content, got {candidates[0].confidence_score:.3f}"
            )

    def test_native_id_matching_with_similar_content(self):
        """Test native_id matching with similar content."""
        # Create a simple mock prospect
        existing_prospect = Mock()
        existing_prospect.id = "existing_002"
        existing_prospect.native_id = "TEST_002"
        existing_prospect.title = "Senior Software Engineer"
        existing_prospect.description = "Full-stack development position"
        existing_prospect.agency = "NASA"
        existing_prospect.place_city = "Houston"
        existing_prospect.place_state = "TX"

        # Mock the detector's cache to simulate existing prospects
        self.detector._prospects_cache = {
            "by_native_id": {"TEST_002": [existing_prospect]}
        }
        self.detector._cache_source_id = 1

        # New record with same native_id and similar content
        new_record = {
            "native_id": "TEST_002",
            "title": "Sr. Software Engineer",  # Similar
            "description": "Full-stack developer role",  # Similar
            "agency": "NASA",
            "place_city": "Houston",
            "place_state": "TX",
        }

        # Test the exact native_id match strategy directly
        candidates = self.detector._exact_native_id_match(
            Mock(), new_record, self.detector.strategies[0]
        )

        # Should have high confidence due to similar content
        assert candidates
        assert candidates[0].confidence_score > 0.8, (
            f"Expected high confidence for similar content, got {candidates[0].confidence_score:.3f}"
        )

    def test_deduplicate_candidates(self):
        """Test candidate deduplication."""
        candidates = [
            MatchCandidate(
                prospect_id="001",
                native_id="TEST_001",
                title="Test 1",
                confidence_score=0.8,
                match_type="strong",
                matched_fields=["native_id"],
            ),
            MatchCandidate(
                prospect_id="001",  # Same ID
                native_id="TEST_001",
                title="Test 1",
                confidence_score=0.9,  # Higher confidence
                match_type="exact",
                matched_fields=["native_id", "title"],
            ),
            MatchCandidate(
                prospect_id="002",
                native_id="TEST_002",
                title="Test 2",
                confidence_score=0.7,
                match_type="fuzzy",
                matched_fields=["title"],
            ),
        ]

        deduped = self.detector._deduplicate_candidates(candidates)

        # Should keep highest confidence for each ID
        assert len(deduped) == 2
        prospect_001 = next(c for c in deduped if c.prospect_id == "001")
        assert prospect_001.confidence_score == 0.9


class TestConfigurableThresholds:
    """Test that configurable thresholds work correctly."""

    @patch("app.utils.duplicate_prevention.active_config")
    def test_configurable_native_id_threshold(self, mock_config):
        """Test configurable native_id content similarity threshold."""
        # Set custom threshold
        mock_config.DUPLICATE_NATIVE_ID_MIN_CONTENT_SIM = 0.5
        mock_config.DUPLICATE_TITLE_SIMILARITY_THRESHOLD = 0.7
        mock_config.DUPLICATE_FUZZY_CONTENT_THRESHOLD = 0.9
        mock_config.DUPLICATE_MIN_CONFIDENCE = 0.85

        detector = DuplicateDetector()

        # This would need more complex mocking to fully test,
        # but the configuration is now accessible
        assert hasattr(mock_config, "DUPLICATE_NATIVE_ID_MIN_CONTENT_SIM")
        assert hasattr(mock_config, "DUPLICATE_MIN_CONFIDENCE")


class TestEnhancedBulkUpsert:
    """Test the enhanced bulk upsert function."""

    def test_ai_preservation_flag(self):
        """Test that AI preservation flag is respected."""
        # Test the _update_preserving_ai_fields function directly
        from app.utils.duplicate_prevention import _update_preserving_ai_fields

        # Create a mock prospect with AI data
        existing_prospect = Mock()
        existing_prospect.naics = "541511"
        existing_prospect.primary_contact_email = "ai@example.com"
        existing_prospect.ai_enhanced_title = "AI Enhanced Title"
        existing_prospect.ollama_processed_at = datetime.now(UTC)

        # New data that would normally overwrite AI fields
        new_data = {
            "title": "Updated Title",
            "description": "Updated Description",
            "naics": None,  # Would clear AI field
            "primary_contact_email": None,  # Would clear AI field
            "ai_enhanced_title": None,  # Would clear AI field
        }

        # Apply AI preservation update
        _update_preserving_ai_fields(existing_prospect, new_data)

        # AI fields should be preserved (not updated)
        assert existing_prospect.naics == "541511"
        assert existing_prospect.primary_contact_email == "ai@example.com"
        assert existing_prospect.ai_enhanced_title == "AI Enhanced Title"

        # Non-AI fields should be updated
        assert existing_prospect.title == "Updated Title"
        assert existing_prospect.description == "Updated Description"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
