import re
from datetime import datetime

import pandas as pd

from app.utils.logger import logger


def parse_value_range(value_str):
    """Parses common value range strings into a numeric value and a unit string."""
    if pd.isna(value_str):
        return pd.NA, pd.NA
    value_str_orig = str(value_str).strip()  # Keep original for unit if unparsed
    value_str = value_str_orig.upper().replace(",", "")

    # Explicitly check for TBD
    if value_str == "TBD":
        # Return NA for numeric value, NA for unit. Suppresses warning.
        return pd.NA, pd.NA

    numeric_val, unit_str = (
        pd.NA,
        value_str_orig,
    )  # Default unit is original string if unparsed

    # --- Start existing parsing logic ---
    try:
        numeric_val = float(value_str.replace("$", ""))
        unit_str = None  # Successfully parsed as number, no unit needed
        return numeric_val, unit_str
    except ValueError:
        pass

    # Define multipliers
    multipliers = {"K": 1000, "THOUSAND": 1000, "M": 1000000, "MILLION": 1000000}
    unit_pattern = r"(K|THOUSAND|M|MILLION)?"

    # Regex patterns:
    # 1. Range pattern
    range_pattern = re.compile(
        rf"(?:BETWEEN\s*\$?|\$?)(?P<low>[\d.]+)\s*{unit_pattern}\s*(?:-|TO|AND)\s*\$?\s*(?P<high>[\d.]+)\s*{unit_pattern}"
    )
    # 2. Threshold pattern (Updated to include >=, <=, < OR =, > OR =)
    threshold_pattern = re.compile(
        rf"(?:OVER|UNDER|LESS THAN|>=|<=|>|<|< OR =|> OR =)\s*\$?(?P<thresh>[\d.]+)\s*{unit_pattern}"
    )
    # 3. Simple Number + Unit pattern
    simple_unit_pattern = re.compile(rf"\$?([\d.]+)\s*{unit_pattern}")

    range_match = range_pattern.search(value_str)
    threshold_match = threshold_pattern.search(value_str)
    simple_unit_match = simple_unit_pattern.match(value_str)

    if range_match:
        low_val = float(range_match.group("low"))
        low_unit = range_match.group(
            2
        )  # Group index might change based on pattern structure
        numeric_val = low_val * multipliers.get(low_unit, 1)
        unit_str = value_str_orig  # Store original range string as unit
    elif threshold_match:
        val = float(threshold_match.group("thresh"))
        unit = threshold_match.group(2)  # Group index might change
        numeric_val = val * multipliers.get(unit, 1)
        unit_str = value_str_orig  # Store original threshold string as unit
    elif simple_unit_match:
        # Need to adjust group indices if unit_pattern changes captures
        val = float(simple_unit_match.group(1))
        unit = simple_unit_match.group(2)  # Assuming unit is the second capture group
        if unit:
            numeric_val = val * multipliers.get(unit, 1)
            unit_str = unit
        else:  # It matched as a simple number without unit (already tried float conversion)
            # This case should ideally be caught by the initial float() try block,
            # but if it somehow reaches here, treat as unparsed.
            numeric_val = pd.NA
            unit_str = value_str_orig  # Keep original as unit
    else:
        # Value string did not match any pattern and wasn't a simple float
        # Keep defaults: numeric_val = pd.NA, unit_str = value_str_orig
        pass  # Keep NA, original value

    return numeric_val, unit_str


def fiscal_quarter_to_date(qtr_str):
    """Converts FY/Quarter string to a representative date and extracts the fiscal year.
    Returns a tuple: (pd.Timestamp, fiscal_year).
    Returns (pd.NaT, pd.NA) on failure or TBD.
    """
    if pd.isna(qtr_str):
        return pd.NaT, pd.NA  # Return tuple
    qtr_str_orig = str(qtr_str).strip()
    qtr_str = qtr_str_orig.upper()

    # Explicitly check for TBD
    if qtr_str == "TBD":
        return pd.NaT, pd.NA  # Return tuple

    # Updated regex to handle 'Qn' or 'Nth' formats, with year potentially before or after.
    match = re.search(
        r"(?:FY)?(\d{2,4})?\s*(?:Q([1-4])|([1-4])(?:ST|ND|RD|TH))|(?:Q([1-4])|([1-4])(?:ST|ND|RD|TH))\s*(?:FY)?(\d{2,4})?",
        qtr_str,
    )
    if match:
        # Extract year and quarter from potentially different groups
        year_part = match.group(1) or match.group(6)
        quarter_part = (
            match.group(2) or match.group(3) or match.group(4) or match.group(5)
        )

        if quarter_part:
            quarter, current_year = int(quarter_part), datetime.now().year
            year = current_year
            if year_part:
                year = 2000 + int(year_part) if int(year_part) < 100 else int(year_part)
            # Adjust month based on fiscal quarter start (Oct = Q1, Jan = Q2, Apr = Q3, Jul = Q4)
            # Target the *start* of the quarter
            if quarter == 1:
                month, year_offset = 10, -1  # Q1 starts in previous calendar year
            elif quarter == 2:
                month, year_offset = 1, 0
            elif quarter == 3:
                month, year_offset = 4, 0
            elif quarter == 4:
                month, year_offset = 7, 0
            else:  # Should not happen due to regex
                logger.warning(
                    f"Invalid quarter number {quarter} parsed from '{qtr_str_orig}'"
                )
                return pd.NaT, pd.NA  # Return tuple

            fiscal_year = year  # Use the derived/provided year as the fiscal year
            calendar_year = fiscal_year + year_offset

            try:
                # Return both the timestamp and the fiscal year
                return pd.Timestamp(f"{calendar_year}-{month:02d}-01"), fiscal_year
            except ValueError:
                logger.warning(
                    f"Date formation error Y={calendar_year}, M={month} from '{qtr_str_orig}'"
                )  # Log original string
                return pd.NaT, pd.NA  # Return tuple on date creation error
    # Log warning only if it wasn't handled (i.e., not TBD and didn't match/parse correctly)
    logger.warning(
        f"Could not parse fiscal quarter: {qtr_str_orig}"
    )  # Log original string
    return pd.NaT, pd.NA  # Return tuple on regex failure or other parse issues


def normalize_naics_code(naics_str):
    """Normalizes NAICS codes to consistent format without decimals or descriptions."""
    if pd.isna(naics_str):
        return pd.NA

    naics_str = str(naics_str).strip()

    # Handle empty string
    if not naics_str:
        return pd.NA

    # Handle TBD placeholder values from data sources
    if naics_str.upper() in ["TBD", "TO BE DETERMINED", "N/A", "NA"]:
        return pd.NA

    # Remove any decimal point and trailing zeros (e.g., "237310.0" -> "237310")
    if "." in naics_str:
        naics_str = naics_str.split(".")[0]

    # Extract numeric code if description is included (e.g., "541519 - Other Computer Related Services" -> "541519")
    # Look for pattern of digits followed by space and dash
    match = re.match(r"^(\d+)(?:\s*-.*)?$", naics_str)
    if match:
        naics_str = match.group(1)

    # Verify it's a valid NAICS code (should be numeric and typically 2-6 digits)
    if naics_str.isdigit() and 2 <= len(naics_str) <= 6:
        return naics_str
    logger.warning(f"Invalid NAICS code format: {naics_str}")
    return pd.NA


def split_place(place_str):
    """Splits a place string into City and State, handling common variations."""
    if pd.isna(place_str):
        return pd.NA, pd.NA

    cleaned_str = str(place_str).replace("[", "").replace("]", "").strip()

    # Handle specific known non-city places first (case-insensitive checks)
    cleaned_upper = cleaned_str.upper()
    if cleaned_upper == "NATIONWIDE":
        return "Nationwide", pd.NA
    if "TBD" in cleaned_upper:
        # Return "TBD" explicitly for place as well? Or keep NA? Let's keep NA for now.
        return pd.NA, pd.NA
    # Handle specific territory/common non-standard formats
    if cleaned_upper == "PUERTO RICO, UNITED STATES" or cleaned_upper == "PUERTO RICO":
        return pd.NA, "PR"
    # Add other territories if needed, e.g.:
    # if cleaned_upper == 'GUAM, UNITED STATES' or cleaned_upper == 'GUAM':
    #     return pd.NA, "GU"

    # Check for multi-state format (e.g., AZ, CA, OK, TX)
    parts_upper = [p.strip() for p in cleaned_upper.split(",") if p.strip()]
    is_multi_state = len(parts_upper) > 1 and all(
        len(p) <= 3 and p.isalpha() for p in parts_upper
    )
    if is_multi_state:
        logger.info(
            f"Detected multi-state place: {place_str}. Storing original string in state."
        )
        return pd.NA, place_str.strip()

    # Proceed with standard City, State or State parsing (using original case string)
    parts = [p.strip() for p in cleaned_str.split(",") if p.strip()]
    if len(parts) == 2:
        city, state_part = parts[0], parts[1]
        # Handle "State, United States" format where State is likely an abbreviation
        if state_part.upper() == "UNITED STATES" and len(city) <= 3 and city.isalpha():
            return pd.NA, city.upper()
        # Standard City, State format check
        if len(state_part) <= 3 and state_part.isalpha():
            return city.title(), state_part.upper()
        logger.warning(
            f"Unexpected place format '{place_str}', treating as city: {city}"
        )
        return city.title(), pd.NA
    if len(parts) == 1:
        part = parts[0]
        if len(part) <= 3 and part.isalpha():
            return pd.NA, part.upper()
        return part.title(), pd.NA
    logger.warning(f"Could not confidently split place: {place_str}")
    return pd.NA, pd.NA
