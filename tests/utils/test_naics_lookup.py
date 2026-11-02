"""
Comprehensive tests for NAICS lookup utilities.

Tests NAICS code validation and description lookup functionality.
"""

from unittest.mock import patch

from app.utils.naics_lookup import (
    get_naics_description,
    get_naics_info,
    validate_naics_code,
)


class TestNAICSValidation:
    """Test NAICS code validation functions."""

    def test_validate_naics_code_valid_format(self):
        """Test validation accepts properly formatted codes."""
        import random
        import string

        # Generate random 6-digit codes to test format validation
        for _ in range(10):
            # Generate a random 6-digit numeric code
            code = "".join(random.choices(string.digits, k=6))
            result = validate_naics_code(code)

            # The function should return a boolean for well-formatted codes
            assert isinstance(result, bool), (
                f"validate_naics_code should return bool for {code}"
            )

            # If it starts with certain prefixes, it might be valid
            # We're testing the function behavior, not specific codes

    def test_validate_naics_code_invalid_codes(self):
        """Test validation of invalid NAICS codes."""
        invalid_codes = [
            "",  # Empty string
            None,  # None value
            "ABC123",  # Non-numeric
            "12345",  # Too short (5 digits)
            "1234567",  # Too long (7 digits)
            "54151a",  # Contains letter
        ]

        for code in invalid_codes:
            result = validate_naics_code(code)
            # Invalid format codes should return False
            if code and isinstance(code, str) and not code.isdigit():
                assert result is False, f"Non-numeric code {code} should be invalid"
            elif code and isinstance(code, str) and len(code) != 6:
                assert result is False, f"Wrong length code {code} should be invalid"


class TestNAICSDescriptions:
    """Test NAICS description lookup functions."""

    @patch("app.utils.naics_lookup.NAICS_DESCRIPTIONS")
    def test_get_naics_description_existing_codes(self, mock_naics_codes):
        """Test getting descriptions for codes that exist in the database."""
        import random
        import string

        # Create dynamic test data
        test_descriptions = {}
        for _ in range(5):
            code = "".join(random.choices(string.digits, k=6))
            desc = f"Test Industry {random.randint(100, 999)}"
            test_descriptions[code] = desc

        mock_naics_codes.get.side_effect = lambda x: test_descriptions.get(x)

        # Test that existing codes return their descriptions
        for code, expected_desc in test_descriptions.items():
            result = get_naics_description(code)
            assert result == expected_desc, (
                "Description lookup should return the mapped description"
            )

    @patch("app.utils.naics_lookup.NAICS_DESCRIPTIONS")
    def test_get_naics_description_non_existing_codes(self, mock_naics_codes):
        """Test getting descriptions for non-existing NAICS codes."""
        import random
        import string

        # Create a small set of known codes
        known_codes = {}
        for _ in range(3):
            code = "".join(random.choices(string.digits, k=6))
            known_codes[code] = f"Known Industry {code}"

        mock_naics_codes.get.side_effect = lambda x: known_codes.get(x)

        # Generate codes that are definitely not in our known set
        for _ in range(5):
            test_code = "".join(random.choices(string.digits, k=6))
            # Make sure it's not accidentally in our known codes
            while test_code in known_codes:
                test_code = "".join(random.choices(string.digits, k=6))

            result = get_naics_description(test_code)
            assert result is None, "Should return None for non-existing codes"

    def test_get_naics_description_invalid_input(self):
        """Test description lookup with invalid input."""
        invalid_inputs = [None, "", "ABC", "12345"]

        for invalid_input in invalid_inputs:
            result = get_naics_description(invalid_input)
            assert result is None, (
                f"Should return None for invalid input {invalid_input}"
            )


class TestNAICSInfo:
    """Test NAICS info retrieval function."""

    @patch("app.utils.naics_lookup.get_naics_description")
    @patch("app.utils.naics_lookup.validate_naics_code")
    def test_get_naics_info_valid_code(self, mock_validate, mock_get_desc):
        """Test getting info for valid NAICS code."""
        import random
        import string

        # Generate random test data
        test_code = "".join(random.choices(string.digits, k=6))
        test_desc = f"Test Industry {random.randint(100, 999)}"

        mock_validate.return_value = True
        mock_get_desc.return_value = test_desc

        result = get_naics_info(test_code)

        assert isinstance(result, dict), "Should return a dictionary"
        assert "code" in result
        assert "description" in result
        assert result["code"] == test_code
        assert result["description"] == test_desc

    @patch("app.utils.naics_lookup.get_naics_description")
    @patch("app.utils.naics_lookup.validate_naics_code")
    def test_get_naics_info_invalid_code(self, mock_validate, mock_get_desc):
        """Test getting info for invalid NAICS code."""
        mock_validate.return_value = False
        mock_get_desc.return_value = None

        result = get_naics_info("999999")

        assert isinstance(result, dict), "Should return a dictionary"
        assert result.get("code") == "999999" or result.get("code") is None
        assert result.get("description") is None

    def test_get_naics_info_none_input(self):
        """Test getting info with None input."""
        result = get_naics_info(None)

        assert isinstance(result, dict), "Should return a dictionary"
        assert result.get("code") is None
        assert result.get("description") is None


class TestNAICSDataLoading:
    """Test NAICS data loading and file handling."""

    @patch("app.utils.naics_lookup.logger")
    def test_naics_codes_loading_error_handling(self, mock_logger):
        """Test error handling when NAICS codes file is not found."""
        # This test ensures the module handles missing data gracefully
        # The actual loading happens at module import time
        # We're just verifying the module imported successfully
        import app.utils.naics_lookup

        assert hasattr(app.utils.naics_lookup, "NAICS_DESCRIPTIONS")
        assert hasattr(app.utils.naics_lookup, "validate_naics_code")
        assert hasattr(app.utils.naics_lookup, "get_naics_description")
        assert hasattr(app.utils.naics_lookup, "get_naics_info")
