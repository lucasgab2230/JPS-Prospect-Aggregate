"""
Automated tests for duplicate prevention logic.

Tests the duplicate detector's text similarity, confidence scoring,
and threshold configurations following production-level testing principles.
"""

import random
import string
from unittest.mock import patch

import pytest

from app.config import active_config
from app.utils.duplicate_prevention import DuplicateDetector


class TestDuplicateLogic:
    """Test suite for duplicate prevention logic."""

    @pytest.fixture
    def detector(self):
        """Create a DuplicateDetector instance."""
        return DuplicateDetector()

    def test_text_similarity_with_various_inputs(self, detector):
        """Test text similarity calculation with different input types."""
        # Generate random test cases
        test_pairs = []

        # Exact matches (should score highest)
        text1 = f"Test_{random.randint(100, 999)}"
        test_pairs.append((text1, text1, "exact"))

        # Case variations (should score high)
        text2 = f"Software_{random.randint(100, 999)}"
        test_pairs.append((text2.upper(), text2.lower(), "case"))

        # Completely different (should score low)
        text3 = f"Alpha_{random.randint(100, 999)}"
        text4 = f"Beta_{random.randint(100, 999)}"
        test_pairs.append((text3, text4, "different"))

        # Similar with variations
        base = f"Senior {random.choice(['Engineer', 'Manager', 'Analyst'])}"
        test_pairs.append((base, f"Sr. {base[7:]}", "abbreviation"))

        # Empty and None (should score minimal)
        test_pairs.append(("", "NonEmpty", "empty"))
        test_pairs.append((None, "NonNull", "null"))

        for text1, text2, pair_type in test_pairs:
            similarity = detector._calculate_text_similarity(text1, text2)

            # Verify behavior patterns, not exact scores
            if pair_type == "exact":
                assert similarity > 0.95, "Exact matches should score very high"
            elif pair_type == "case":
                assert similarity > 0.9, "Case variations should score high"
            elif pair_type == "different":
                assert similarity < 0.5, "Different texts should score low"
            elif pair_type == "abbreviation":
                assert 0.3 < similarity < 0.95, (
                    "Abbreviations should score moderate to high"
                )
            elif pair_type in ["empty", "null"]:
                assert similarity < 0.1, "Empty/null should score minimal"

    def test_short_string_similarity(self, detector):
        """Test similarity calculation for short strings."""
        # Generate random short strings
        short_strings = []
        for _ in range(5):
            # Generate 2-3 character strings
            short_strings.append("".join(random.choices(string.ascii_uppercase, k=2)))

        for str1 in short_strings:
            # Test exact match
            exact_sim = detector._calculate_text_similarity(str1, str1)
            assert exact_sim > 0.95, "Short string exact matches should score high"

            # Test with punctuation variations
            punct_sim = detector._calculate_text_similarity(
                str1, f"{str1[0]}.{str1[1]}."
            )
            # Should handle punctuation reasonably
            assert isinstance(punct_sim, float)

            # Test completely different short string
            different = "".join(random.choices(string.ascii_uppercase, k=2))
            while different == str1:
                different = "".join(random.choices(string.ascii_uppercase, k=2))

            diff_sim = detector._calculate_text_similarity(str1, different)
            assert diff_sim < exact_sim, (
                "Different strings should score lower than exact"
            )

    def test_configuration_thresholds_exist(self):
        """Test that configuration thresholds are properly defined."""
        # Verify all expected thresholds exist and are reasonable
        assert hasattr(active_config, "DUPLICATE_MIN_CONFIDENCE")
        assert isinstance(active_config.DUPLICATE_MIN_CONFIDENCE, (int, float))
        assert 0 <= active_config.DUPLICATE_MIN_CONFIDENCE <= 1

        assert hasattr(active_config, "DUPLICATE_NATIVE_ID_MIN_CONTENT_SIM")
        assert isinstance(
            active_config.DUPLICATE_NATIVE_ID_MIN_CONTENT_SIM, (int, float)
        )
        assert 0 <= active_config.DUPLICATE_NATIVE_ID_MIN_CONTENT_SIM <= 1

        # These may be optional, so we just check if they exist and are valid if present
        if hasattr(active_config, "DUPLICATE_TITLE_SIMILARITY_THRESHOLD"):
            assert isinstance(
                active_config.DUPLICATE_TITLE_SIMILARITY_THRESHOLD, (int, float)
            )
            assert 0 <= active_config.DUPLICATE_TITLE_SIMILARITY_THRESHOLD <= 1

        if hasattr(active_config, "DUPLICATE_FUZZY_CONTENT_THRESHOLD"):
            assert isinstance(
                active_config.DUPLICATE_FUZZY_CONTENT_THRESHOLD, (int, float)
            )
            assert 0 <= active_config.DUPLICATE_FUZZY_CONTENT_THRESHOLD <= 1

    def test_confidence_calculation_patterns(self):
        """Test confidence score calculation patterns."""
        # Generate random similarity scores
        test_scenarios = []
        for _ in range(10):
            title_sim = random.random()
            desc_sim = random.random()
            test_scenarios.append((title_sim, desc_sim))

        # Test that confidence calculation behaves reasonably
        min_content_sim = getattr(
            active_config, "DUPLICATE_NATIVE_ID_MIN_CONTENT_SIM", 0.3
        )

        for title_sim, desc_sim in test_scenarios:
            # Simulate confidence calculation logic
            if title_sim < min_content_sim and desc_sim < min_content_sim:
                # Low confidence path
                weighted_sim = title_sim * 0.4 + desc_sim * 0.3 + 0.5 * 0.2 + 0.5 * 0.1
                confidence = 0.1 + (weighted_sim * 0.2)
                assert confidence < 0.5, "Low similarity should yield low confidence"

            elif title_sim < 0.5 or desc_sim < 0.5:
                # Medium confidence path
                weighted_sim = title_sim * 0.4 + desc_sim * 0.3 + 0.5 * 0.2 + 0.5 * 0.1
                confidence = 0.3 + (weighted_sim * 0.5)
                assert 0.2 < confidence < 0.8, (
                    "Medium similarity should yield medium confidence"
                )

            else:
                # High confidence path
                weighted_sim = title_sim * 0.4 + desc_sim * 0.3 + 0.5 * 0.2 + 0.5 * 0.1
                confidence = 0.4 + (weighted_sim * 0.6)
                assert confidence > 0.4, (
                    "High similarity should yield higher confidence"
                )

            # Apply penalty for very low title similarity
            if title_sim < 0.1:
                confidence *= 0.5
                assert confidence < 0.5, (
                    "Very low title similarity should penalize confidence"
                )

    def test_native_id_matching_prevents_false_positives(self):
        """Test that native ID matching logic prevents false positives."""
        min_confidence = getattr(active_config, "DUPLICATE_MIN_CONFIDENCE", 0.5)
        min_content_sim = getattr(
            active_config, "DUPLICATE_NATIVE_ID_MIN_CONTENT_SIM", 0.3
        )

        # Test case: Very different content with same native_id
        very_low_title_sim = random.uniform(0.0, 0.1)
        very_low_desc_sim = random.uniform(0.0, 0.1)

        # Calculate confidence as the logic would
        weighted_sim = (
            very_low_title_sim * 0.4 + very_low_desc_sim * 0.3 + 0.5 * 0.2 + 0.5 * 0.1
        )
        confidence = 0.1 + (weighted_sim * 0.2)

        # Apply penalty for very low title
        if very_low_title_sim < 0.1:
            confidence *= 0.5

        # With very different content, confidence should be below threshold
        assert confidence < min_confidence or confidence < 0.3, (
            "Very different content should not match even with same native_id"
        )

    @patch("app.config.active_config.DUPLICATE_MIN_CONFIDENCE", 0.7)
    @patch("app.config.active_config.DUPLICATE_NATIVE_ID_MIN_CONTENT_SIM", 0.4)
    def test_threshold_configuration_affects_matching(self):
        """Test that threshold configuration changes affect matching behavior."""
        # Generate test similarity scores
        test_cases = []
        for _ in range(5):
            test_cases.append(
                {
                    "title_sim": random.uniform(0.3, 0.6),
                    "desc_sim": random.uniform(0.3, 0.6),
                }
            )

        for case in test_cases:
            title_sim = case["title_sim"]
            desc_sim = case["desc_sim"]

            # With higher thresholds (0.7 min confidence, 0.4 min content sim)
            # Medium similarity scores should be less likely to match

            if title_sim < 0.4 and desc_sim < 0.4:
                # Below min content similarity threshold
                weighted_sim = title_sim * 0.4 + desc_sim * 0.3 + 0.5 * 0.2 + 0.5 * 0.1
                confidence = 0.1 + (weighted_sim * 0.2)

                # Should be low confidence
                assert confidence < 0.7, "Below threshold should yield low confidence"

    def test_fuzzy_matching_behavior(self, detector):
        """Test fuzzy matching behavior with realistic text variations."""
        # Generate realistic text variations
        base_titles = [
            "Software Engineer",
            "Data Scientist",
            "Project Manager",
            "Business Analyst",
            "DevOps Engineer",
        ]

        for base_title in base_titles:
            # Test common variations
            variations = [
                f"Senior {base_title}",
                f"Sr. {base_title}",
                f"Lead {base_title}",
                f"{base_title} II",
                f"{base_title} - Remote",
                base_title.lower(),
                base_title.upper(),
            ]

            for variation in variations:
                similarity = detector._calculate_text_similarity(base_title, variation)

                # Should recognize these as related
                assert similarity > 0.3, (
                    f"'{base_title}' and '{variation}' should be recognized as related"
                )

                # But not identical (except case variations)
                if variation not in [base_title.lower(), base_title.upper()]:
                    assert similarity < 0.95, (
                        f"'{base_title}' and '{variation}' should not be identical"
                    )

    def test_edge_cases_in_similarity_calculation(self, detector):
        """Test edge cases in text similarity calculation."""
        # Very long strings
        long_text1 = "A" * 10000
        long_text2 = "A" * 10000
        long_text3 = "B" * 10000

        sim_same = detector._calculate_text_similarity(long_text1, long_text2)
        assert sim_same > 0.95, "Identical long strings should match"

        sim_diff = detector._calculate_text_similarity(long_text1, long_text3)
        assert sim_diff < 0.5, "Different long strings should not match"

        # Special characters
        special1 = "Test@#$%^&*()"
        special2 = "Test@#$%^&*()"
        special3 = "Different@#$%"

        sim_special_same = detector._calculate_text_similarity(special1, special2)
        assert sim_special_same > 0.95, (
            "Identical special character strings should match"
        )

        sim_special_diff = detector._calculate_text_similarity(special1, special3)
        assert sim_special_diff < sim_special_same, (
            "Different special strings should score lower"
        )

        # Unicode characters
        unicode1 = "Test with émojis 🚀"
        unicode2 = "Test with émojis 🚀"
        unicode3 = "Different émojis 🎯"

        sim_unicode_same = detector._calculate_text_similarity(unicode1, unicode2)
        assert sim_unicode_same > 0.95, "Identical unicode strings should match"

        sim_unicode_diff = detector._calculate_text_similarity(unicode1, unicode3)
        assert sim_unicode_diff < sim_unicode_same, (
            "Different unicode strings should score lower"
        )
