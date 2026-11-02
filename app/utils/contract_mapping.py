"""Contract Data Mapping Utilities

Replaces ContractMapperService with simple utility functions.
Handles mapping from various government contract sources to standardized schema.
"""

import hashlib
import re
from datetime import UTC

UTC = UTC
from datetime import datetime

from app.database.models import Prospect
from app.utils.logger import logger


def generate_prospect_id(data: dict) -> str:
    """Generate unique ID for prospect based on key fields."""
    key_parts = [
        str(data.get("title", "")),
        str(data.get("agency", "")),
        str(data.get("source_file", "")),
        str(data.get("native_id", "")),
    ]
    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


def map_universal_fields(record: dict, source_file: str, source_mapping: dict) -> dict:
    """Map source-specific fields to universal schema.
    Extracts NAICS from source data where available.
    """
    # Extract core fields using source-specific mapping
    mapped_data = {
        "title": record.get(source_mapping.get("title_field")),
        "description": record.get(source_mapping.get("description_field")),
        "agency": record.get(source_mapping.get("agency_field"))
        or source_mapping.get("default_agency"),
        "estimated_value_text": record.get(source_mapping.get("value_field")),
        "source_file": source_file,
        "native_id": record.get(source_mapping.get("id_field")),
        "naics": record.get(source_mapping.get("naics_field")),
        "contract_type": record.get(source_mapping.get("contract_type_field")),
        "set_aside": record.get(source_mapping.get("set_aside_field")),
        "place_city": record.get(source_mapping.get("place_city_field")),
        "place_state": record.get(source_mapping.get("place_state_field")),
        "place_country": record.get(source_mapping.get("place_country_field")),
        "primary_contact_email": record.get(source_mapping.get("contact_email_field")),
        "primary_contact_name": record.get(source_mapping.get("contact_name_field")),
    }

    # Handle date fields
    if "release_date_field" in source_mapping:
        mapped_data["release_date_raw"] = record.get(
            source_mapping["release_date_field"]
        )
    if "award_date_field" in source_mapping:
        mapped_data["award_date_raw"] = record.get(source_mapping["award_date_field"])

    # Generate unique ID
    mapped_data["id"] = generate_prospect_id(mapped_data)

    # Clean empty strings to None
    for key, value in mapped_data.items():
        if isinstance(value, str) and value.strip() == "":
            mapped_data[key] = None

    return mapped_data


def create_prospect_from_data(mapped_data: dict, source_id: int) -> Prospect:
    """Create a Prospect object from mapped data."""
    # Handle extra data (non-core fields)
    extra_data = {}
    core_fields = {
        "id",
        "title",
        "description",
        "agency",
        "estimated_value_text",
        "source_file",
        "native_id",
        "naics",
        "contract_type",
        "set_aside",
        "place_city",
        "place_state",
        "place_country",
        "primary_contact_email",
        "primary_contact_name",
        "release_date_raw",
        "award_date_raw",
    }

    for key, value in mapped_data.items():
        if key not in core_fields and value is not None:
            extra_data[key] = value

    prospect = Prospect(
        id=mapped_data["id"],
        title=mapped_data.get("title"),
        description=mapped_data.get("description"),
        agency=mapped_data.get("agency"),
        estimated_value_text=mapped_data.get("estimated_value_text"),
        native_id=mapped_data.get("native_id"),
        naics=mapped_data.get("naics"),
        contract_type=mapped_data.get("contract_type"),
        set_aside=mapped_data.get("set_aside"),
        place_city=mapped_data.get("place_city"),
        place_state=mapped_data.get("place_state"),
        place_country=mapped_data.get("place_country"),
        primary_contact_email=mapped_data.get("primary_contact_email"),
        primary_contact_name=mapped_data.get("primary_contact_name"),
        source_id=source_id,
        loaded_at=datetime.now(UTC),
        extra=extra_data if extra_data else None,
    )

    return prospect


def bulk_map_and_create_prospects(
    records: list[dict], source_mapping: dict, source_id: int, source_file: str
) -> list[Prospect]:
    """Bulk process records into prospects.
    Returns list of Prospect objects ready for database insertion.
    """
    prospects = []

    for record in records:
        try:
            mapped_data = map_universal_fields(record, source_file, source_mapping)
            prospect = create_prospect_from_data(mapped_data, source_id)
            prospects.append(prospect)
        except Exception as e:
            logger.error(f"Error mapping record to prospect: {e}")
            logger.debug(f"Problematic record: {record}")
            continue

    return prospects


def extract_naics_from_text(text: str) -> str | None:
    """Extract NAICS code from text using regex patterns."""
    if not text:
        return None

    # Look for 6-digit NAICS codes
    naics_patterns = [
        r"\b(\d{6})\b",  # Standalone 6-digit number
        r"NAICS[:\s]*(\d{6})",  # "NAICS: 123456" or "NAICS 123456"
        r"(\d{6})\s*[-|]\s*",  # "123456 - Description"
    ]

    for pattern in naics_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            naics_code = match.group(1)
            # Validate NAICS code (should start with 1-9, not 0)
            if naics_code[0] in "123456789":
                return naics_code

    return None


def standardize_agency_name(agency: str) -> str:
    """Standardize agency names for consistency."""
    if not agency:
        return agency

    # Common agency name standardizations
    standardizations = {
        "DHS": "Department of Homeland Security",
        "HHS": "Health and Human Services",
        "DOT": "Department of Transportation",
        "DOC": "Department of Commerce",
        "DOJ": "Department of Justice",
        "DOS": "Department of State",
        "Treasury": "Department of Treasury",
        "SSA": "Social Security Administration",
        "GSA": "General Services Administration",
    }

    agency_upper = agency.upper().strip()

    for abbrev, full_name in standardizations.items():
        if agency_upper == abbrev or agency_upper == full_name.upper():
            return full_name

    return agency.strip()


def validate_mapped_data(mapped_data: dict) -> list[str]:
    """Validate mapped data and return list of validation errors.
    Returns empty list if data is valid.
    """
    errors = []

    # Required fields check
    if not mapped_data.get("title"):
        errors.append("Title is required")

    if not mapped_data.get("agency"):
        errors.append("Agency is required")

    # NAICS validation
    naics = mapped_data.get("naics")
    if naics and not re.match(r"^\d{6}$", str(naics)):
        errors.append(f"Invalid NAICS code format: {naics}")

    # Email validation
    email = mapped_data.get("primary_contact_email")
    if email and not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        errors.append(f"Invalid email format: {email}")

    return errors
