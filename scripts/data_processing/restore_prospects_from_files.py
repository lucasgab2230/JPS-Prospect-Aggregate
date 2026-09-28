#!/usr/bin/env python3
"""Restore prospects from the most recent raw files in each agency directory.

This script finds the most recent file for each agency and imports the prospects
into the database using the same data processing logic as the scrapers.
"""

import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add the app directory to the Python path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))

from app import create_app
from app.core.scraper_configs import get_scraper_config
from app.database import db
from app.database.crud import bulk_upsert_prospects
from app.database.models import DataSource
from app.utils.logger import logger

# Mapping of directory names to database scraper keys
DIRECTORY_TO_SCRAPER_KEY = {
    "acqgw": "ACQGW",
    "dhs": "DHS",
    "doc": "DOC",
    "doj": "DOJ",
    "dos": "DOS",
    "dot": "DOT",
    "hhs": "HHS",
    "ssa": "SSA",
    "treas": "TREAS",
}

# Mapping of directory names to scraper config keys
DIRECTORY_TO_CONFIG_KEY = {
    "acqgw": "acquisition_gateway",
    "dhs": "dhs",
    "doc": "doc",
    "doj": "doj",
    "dos": "dos",
    "dot": "dot",
    "hhs": "hhs",
    "ssa": "ssa",
    "treas": "treasury",
}

# File extensions by agency
FILE_EXTENSIONS = {
    "acqgw": "*.csv",
    "dhs": "*.csv",
    "doc": "*.xlsx",
    "doj": "*.xlsx",
    "dos": "*.xlsx",
    "dot": "*.csv",
    "hhs": "*.csv",
    "ssa": "*.xlsm",
    "treas": "*.xls",
}


def extract_timestamp_from_filename(filename: str) -> datetime | None:
    """Extract timestamp from filename using standard format."""
    # Look for pattern like 'agency_YYYYMMDD_HHMMSS.ext'
    match = re.search(r"(\d{8}_\d{6})", filename)
    if match:
        timestamp_str = match.group(1)
        try:
            return datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
        except ValueError:
            pass
    return None


def find_most_recent_file(directory: Path, pattern: str) -> Path | None:
    """Find the most recent file in a directory matching the pattern."""
    files = list(directory.glob(pattern))
    if not files:
        return None

    # Sort by timestamp extracted from filename
    def get_file_timestamp(file_path):
        timestamp = extract_timestamp_from_filename(file_path.name)
        return timestamp if timestamp else datetime.min

    most_recent = max(files, key=get_file_timestamp)
    return most_recent


def read_file_data(file_path: Path, config: "ScraperConfig") -> pd.DataFrame:
    """Read data from a file based on its extension and scraper config."""
    try:
        if file_path.suffix.lower() == ".csv":
            # Use CSV reading options from scraper config if available
            csv_options = getattr(config, "csv_read_options", {})
            if not csv_options:
                # Default safe CSV reading options
                csv_options = {
                    "encoding": "utf-8",
                    "on_bad_lines": "skip",
                    "quoting": 1,
                    "engine": "python",
                }
            return pd.read_csv(file_path, **csv_options)
        if file_path.suffix.lower() in [".xlsx", ".xls", ".xlsm"]:
            # Use Excel reading options from scraper config if available
            excel_options = getattr(config, "excel_read_options", {})
            return pd.read_excel(file_path, **excel_options)
        raise ValueError(f"Unsupported file type: {file_path.suffix}")
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return pd.DataFrame()


def process_agency_data(
    agency_dir: str, scraper_key: str, config_key: str, source_id: int
) -> bool:
    """Process the most recent file for an agency."""
    data_dir = Path("data/raw") / agency_dir

    if not data_dir.exists():
        logger.error(f"Directory not found: {data_dir}")
        return False

    # Get file pattern for this agency
    file_pattern = FILE_EXTENSIONS.get(agency_dir, "*.csv")

    # Find most recent file
    most_recent_file = find_most_recent_file(data_dir, file_pattern)
    if not most_recent_file:
        logger.error(f"No files found in {data_dir} matching pattern {file_pattern}")
        return False

    logger.info(f"Processing {agency_dir}: {most_recent_file.name}")

    # Get scraper configuration for field mappings
    try:
        config = get_scraper_config(config_key)
    except Exception as e:
        logger.error(f"Error getting scraper config for {config_key}: {e}")
        return False

    # Read the file
    df = read_file_data(most_recent_file, config)
    if df.empty:
        logger.warning(f"No data found in {most_recent_file}")
        return False

    # Apply field mappings and transformations
    try:
        # Apply column mappings from scraper config
        if hasattr(config, "raw_column_rename_map") and config.raw_column_rename_map:
            df = df.rename(columns=config.raw_column_rename_map)

        if hasattr(config, "db_column_rename_map") and config.db_column_rename_map:
            df = df.rename(columns=config.db_column_rename_map)

        # Set standard fields
        df["agency"] = config.source_name
        df["source_id"] = source_id

        # Generate IDs for prospects (using same method as scrapers)
        if "id" not in df.columns:
            df["id"] = df.apply(
                lambda row: generate_prospect_id(row, source_id), axis=1
            )

        # Filter to only valid Prospect columns
        valid_columns = {
            "id",
            "native_id",
            "title",
            "ai_enhanced_title",
            "description",
            "agency",
            "naics",
            "naics_description",
            "naics_source",
            "estimated_value",
            "est_value_unit",
            "estimated_value_text",
            "estimated_value_min",
            "estimated_value_max",
            "estimated_value_single",
            "release_date",
            "award_date",
            "award_fiscal_year",
            "place_city",
            "place_state",
            "place_country",
            "contract_type",
            "set_aside",
            "set_aside_standardized",
            "set_aside_standardized_label",
            "primary_contact_email",
            "primary_contact_name",
            "loaded_at",
            "ollama_processed_at",
            "ollama_model_version",
            "enhancement_status",
            "enhancement_started_at",
            "enhancement_user_id",
            "extra",
            "source_id",
        }

        # Keep only columns that exist in both the dataframe and the model
        columns_to_keep = [col for col in df.columns if col in valid_columns]
        df_filtered = df[columns_to_keep].copy()

        logger.info(f"Kept {len(columns_to_keep)} valid columns: {columns_to_keep}")

        # Insert into database
        logger.info(
            f"Inserting {len(df_filtered)} prospects from {most_recent_file.name}"
        )
        bulk_upsert_prospects(
            df_filtered, preserve_ai_data=True, enable_smart_matching=False
        )

        logger.info(f"Successfully processed {len(df)} prospects from {agency_dir}")
        return True

    except Exception as e:
        logger.error(f"Error processing data for {agency_dir}: {e}")
        return False


def generate_prospect_id(row: pd.Series, source_id: int) -> str:
    """Generate a unique ID for a prospect based on key fields."""
    import hashlib

    # Use native_id if available, otherwise create from key fields
    if pd.notna(row.get("native_id")):
        key_string = f"{source_id}_{row['native_id']}"
    else:
        # Fallback to title + agency if no native_id
        title = str(row.get("title", ""))[:100]  # Limit length
        agency = str(row.get("agency", ""))
        key_string = f"{source_id}_{title}_{agency}"

    return hashlib.md5(key_string.encode("utf-8")).hexdigest()


def restore_all_prospects():
    """Restore prospects from the most recent files for all agencies."""
    app = create_app()

    with app.app_context():
        # Get all data sources
        data_sources = {}
        for source in DataSource.query.all():
            data_sources[source.scraper_key] = source

        logger.info(f"Found {len(data_sources)} data sources in database")

        success_count = 0
        total_agencies = len(DIRECTORY_TO_SCRAPER_KEY)

        # Process each agency
        for agency_dir in DIRECTORY_TO_SCRAPER_KEY:
            logger.info(f"\n--- Processing {agency_dir.upper()} ---")

            scraper_key = DIRECTORY_TO_SCRAPER_KEY[agency_dir]
            config_key = DIRECTORY_TO_CONFIG_KEY[agency_dir]

            if scraper_key not in data_sources:
                logger.error(f"No data source found for scraper key: {scraper_key}")
                continue

            source = data_sources[scraper_key]
            success = process_agency_data(
                agency_dir, scraper_key, config_key, source.id
            )

            if success:
                success_count += 1
            else:
                logger.error(f"Failed to process {agency_dir}")

        logger.info("\n=== RESTORATION COMPLETE ===")
        logger.info(
            f"Successfully processed: {success_count}/{total_agencies} agencies"
        )

        # Show final stats
        from app.database.models import Prospect

        total_prospects = db.session.query(Prospect).count()
        logger.info(f"Total prospects in database: {total_prospects}")


if __name__ == "__main__":
    try:
        restore_all_prospects()
    except KeyboardInterrupt:
        logger.warning("Restoration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error during restoration: {e}")
        sys.exit(1)
