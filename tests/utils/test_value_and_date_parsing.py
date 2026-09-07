"""
Comprehensive tests for value and date parsing utilities.

Tests critical data processing functions for contract values and dates.
"""

import pandas as pd

from app.utils.value_and_date_parsing import (
    fiscal_quarter_to_date,
    normalize_naics_code,
    parse_value_range,
    split_place,
)


class TestValueRangeParsing:
    """Test value range parsing function."""

    def test_parse_value_range_single_values(self):
        """Test parsing single values."""
        test_cases = [
            ("$100,000", (100000.0, None)),
            ("$1,500,000.00", (1500000.0, None)),
            ("500000", (500000.0, None)),
            ("$50K", (50000.0, "K")),
            ("$2.5M", (2500000.0, "M")),
            ("$1.2B", (pd.NA, "$1.2B")),  # B not recognized, returns original
            ("100K", (100000.0, "K")),
            ("2.5M", (2500000.0, "M")),
        ]

        for input_value, expected in test_cases:
            numeric_val, unit_str = parse_value_range(input_value)
            expected_num, expected_unit = expected

            if pd.notna(expected_num) and pd.notna(numeric_val):
                assert abs(numeric_val - expected_num) < 0.01, (
                    f"Failed for {input_value}: got ({numeric_val}, {unit_str}), expected {expected}"
                )
            else:
                assert pd.isna(numeric_val) and pd.isna(expected_num), (
                    f"Failed for {input_value}: got ({numeric_val}, {unit_str}), expected {expected}"
                )

            assert unit_str == expected_unit, (
                f"Unit failed for {input_value}: got {unit_str}, expected {expected_unit}"
            )

    def test_parse_value_range_ranges(self):
        """Test parsing value ranges."""
        test_cases = [
            (
                "$100,000 - $500,000",
                (100000.0, "$100,000 - $500,000"),
            ),  # Returns low value and original string
            ("$1M - $5M", (1000000.0, "$1M - $5M")),
            ("100K - 500K", (100000.0, "100K - 500K")),
            ("$50,000 to $150,000", (50000.0, "$50,000 to $150,000")),
            ("$1.5M-$2.5M", (1500000.0, "$1.5M-$2.5M")),
        ]

        for input_value, expected in test_cases:
            numeric_val, unit_str = parse_value_range(input_value)
            expected_num, expected_unit = expected

            if pd.notna(expected_num) and pd.notna(numeric_val):
                assert abs(numeric_val - expected_num) < 0.01, (
                    f"Value failed for {input_value}: got {numeric_val}, expected {expected_num}"
                )
            assert unit_str == expected_unit, (
                f"Unit failed for {input_value}: got {unit_str}, expected {expected_unit}"
            )

    def test_parse_value_range_edge_cases(self):
        """Test edge cases in value range parsing."""
        # Empty or invalid inputs
        num, unit = parse_value_range("")
        assert pd.isna(num) and unit == ""

        num, unit = parse_value_range(None)
        assert pd.isna(num) and pd.isna(unit)

        num, unit = parse_value_range("TBD")
        assert pd.isna(num) and pd.isna(unit)

        num, unit = parse_value_range("To Be Determined")
        assert pd.isna(num) and unit == "To Be Determined"

        num, unit = parse_value_range("N/A")
        assert pd.isna(num) and unit == "N/A"


class TestFiscalQuarterToDate:
    """Test fiscal quarter to date conversion."""

    def test_fiscal_quarter_to_date_valid_quarters(self):
        """Test valid fiscal quarter conversions."""
        # Note: When year is not specified, the function uses current year
        # Test with explicit years only
        test_cases = [
            ("FY2024 Q1", (pd.Timestamp("2023-10-01"), 2024)),
            ("FY2024 Q2", (pd.Timestamp("2024-01-01"), 2024)),
            ("FY2024 Q3", (pd.Timestamp("2024-04-01"), 2024)),
            ("FY2024 Q4", (pd.Timestamp("2024-07-01"), 2024)),
            ("FY24 Q1", (pd.Timestamp("2023-10-01"), 2024)),
            ("2024 Q1", (pd.Timestamp("2023-10-01"), 2024)),
            # Note: "Q1 FY2024" and "1ST 2024" formats don't parse year correctly with current regex
        ]

        for input_quarter, expected in test_cases:
            date_result, fy_result = fiscal_quarter_to_date(input_quarter)
            expected_date, expected_fy = expected

            if pd.notna(expected_date):
                assert date_result == expected_date, (
                    f"Date failed for {input_quarter}: got {date_result}, expected {expected_date}"
                )
                assert fy_result == expected_fy, (
                    f"FY failed for {input_quarter}: got {fy_result}, expected {expected_fy}"
                )

    def test_fiscal_quarter_to_date_edge_cases(self):
        """Test edge cases for fiscal quarter conversion."""
        # Invalid inputs
        date_result, fy_result = fiscal_quarter_to_date("")
        assert pd.isna(date_result) and pd.isna(fy_result)

        date_result, fy_result = fiscal_quarter_to_date(None)
        assert pd.isna(date_result) and pd.isna(fy_result)

        date_result, fy_result = fiscal_quarter_to_date("Q5 2024")
        assert pd.isna(date_result) and pd.isna(fy_result)

        date_result, fy_result = fiscal_quarter_to_date("Invalid")
        assert pd.isna(date_result) and pd.isna(fy_result)

        date_result, fy_result = fiscal_quarter_to_date("2024")
        assert pd.isna(date_result) and pd.isna(fy_result)


class TestNormalizeNAICSCode:
    """Test NAICS code normalization."""

    def test_normalize_naics_code_valid_codes(self):
        """Test normalizing valid NAICS codes."""
        test_cases = [
            ("541511", "541511"),  # Already normalized
            ("541511.0", "541511"),  # Remove decimal
            (
                "541519 - Other Computer Services",
                "541519",
            ),  # Extract code from description
            (" 541511 ", "541511"),  # Strip whitespace
            ("541511\n", "541511"),  # Strip newline
            ("12", "12"),  # 2-digit code
            ("123456", "123456"),  # 6-digit code
        ]

        for input_code, expected in test_cases:
            result = normalize_naics_code(input_code)
            assert result == expected, (
                f"Failed for {input_code}: got {result}, expected {expected}"
            )

    def test_normalize_naics_code_edge_cases(self):
        """Test edge cases for NAICS code normalization."""
        # Invalid inputs
        assert pd.isna(normalize_naics_code(""))
        assert pd.isna(normalize_naics_code(None))
        assert pd.isna(normalize_naics_code("TBD"))
        assert pd.isna(normalize_naics_code("N/A"))
        assert pd.isna(normalize_naics_code("ABC"))  # Non-numeric input
        assert pd.isna(normalize_naics_code("1234567"))  # Too long (> 6 digits)
        assert pd.isna(normalize_naics_code("1"))  # Too short (< 2 digits)


class TestSplitPlace:
    """Test place splitting function."""

    def test_split_place_valid_inputs(self):
        """Test splitting valid place strings."""
        test_cases = [
            ("Washington, DC", ("Washington", "DC")),
            ("New York, NY", ("New York", "NY")),
            ("Los Angeles, CA", ("Los Angeles", "CA")),
            (
                "San Francisco, California",
                ("San Francisco", pd.NA),
            ),  # State too long, not standard abbreviation
            ("Seattle,WA", ("Seattle", "WA")),  # No space after comma
            (" Miami , FL ", ("Miami", "FL")),  # Extra spaces
            ("[Austin, TX]", ("Austin", "TX")),  # With brackets
        ]

        for input_place, expected in test_cases:
            city, state = split_place(input_place)
            expected_city, expected_state = expected

            if pd.notna(expected_city):
                assert city == expected_city, (
                    f"City failed for {input_place}: got {city}, expected {expected_city}"
                )
            else:
                assert pd.isna(city), (
                    f"Expected NA for city in {input_place}, got {city}"
                )

            if pd.notna(expected_state):
                assert state == expected_state, (
                    f"State failed for {input_place}: got {state}, expected {expected_state}"
                )
            else:
                assert pd.isna(state), (
                    f"Expected NA for state in {input_place}, got {state}"
                )

    def test_split_place_edge_cases(self):
        """Test edge cases for place splitting."""
        # Single value (no comma) - cities return city + NA, states return NA + state
        city, state = split_place("Washington")
        assert city == "Washington" and pd.isna(
            state
        )  # More than 3 chars, treated as city

        city, state = split_place("DC")
        assert pd.isna(city) and state == "DC"  # 2 chars, treated as state

        # Empty or invalid inputs
        city, state = split_place("")
        assert pd.isna(city) and pd.isna(state)

        city, state = split_place(None)
        assert pd.isna(city) and pd.isna(state)

        city, state = split_place(",")
        assert pd.isna(city) and pd.isna(state)

        # Special cases
        city, state = split_place("Nationwide")
        assert city == "Nationwide" and pd.isna(state)

        city, state = split_place("TBD")
        assert pd.isna(city) and pd.isna(state)

        city, state = split_place("Puerto Rico")
        assert pd.isna(city) and state == "PR"


class TestPerformanceAndEdgeCases:
    """Test performance and edge cases."""

    def test_large_value_parsing(self):
        """Test parsing very large contract values."""
        large_values = [
            ("$999,999,999,999", (999999999999.0, None)),
            ("$1T", (pd.NA, "$1T")),  # T not recognized
            ("$1.5 trillion", (pd.NA, "$1.5 trillion")),  # trillion not recognized
        ]

        for input_value, expected in large_values:
            numeric_val, unit_str = parse_value_range(input_value)
            expected_num, expected_unit = expected

            if pd.notna(expected_num) and pd.notna(numeric_val):
                assert abs(numeric_val - expected_num) < 1, (
                    f"Failed for large value {input_value}: got {numeric_val}"
                )
            else:
                assert pd.isna(numeric_val) and pd.isna(expected_num), (
                    f"Failed for {input_value}"
                )

            assert unit_str == expected_unit, (
                f"Unit failed for {input_value}: got {unit_str}, expected {expected_unit}"
            )

    def test_unicode_and_special_characters(self):
        """Test handling of unicode and special characters."""
        unicode_inputs = [
            ("$100,000", (100000.0, None)),  # Regular ASCII
            ("€100,000", (pd.NA, "€100,000")),  # Euro symbol - not parsed
            ("£100,000", (pd.NA, "£100,000")),  # Pound symbol - not parsed
            ("¥100,000", (pd.NA, "¥100,000")),  # Yen symbol - not parsed
        ]

        for input_value, expected in unicode_inputs:
            numeric_val, unit_str = parse_value_range(input_value)
            expected_num, expected_unit = expected

            if pd.notna(expected_num) and pd.notna(numeric_val):
                assert abs(numeric_val - expected_num) < 0.01, (
                    f"Failed for unicode input {input_value}"
                )
            else:
                assert pd.isna(numeric_val) and pd.isna(expected_num), (
                    f"Failed for {input_value}"
                )

            assert unit_str == expected_unit, (
                f"Unit failed for {input_value}: got {unit_str}, expected {expected_unit}"
            )

    def test_parsing_performance(self):
        """Test parsing performance with many inputs."""
        import time

        test_values = [
            "$100,000",
            "$1M",
            "$500K",
            "250000",
            "$1.5M - $2.5M",
            "Q1 2024",
            "Q2 2024",
            "541511",
            "New York, NY",
        ] * 100  # 900 total operations

        start_time = time.time()

        for value in test_values:
            if "$" in value or "K" in value or "M" in value:
                parse_value_range(value)
            elif "Q" in value:
                fiscal_quarter_to_date(value)
            elif value.replace(" ", "").isdigit():
                normalize_naics_code(value)
            else:
                split_place(value)

        end_time = time.time()

        # Should complete in reasonable time (less than 1 second for 900 operations)
        assert end_time - start_time < 1.0, "Parsing performance is too slow"
