#!/usr/bin/env python3
"""Data Extraction Validation Script
Compares raw scraped data files with what should be in the database
to verify accuracy and completeness of data extraction and mapping.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


from app import create_app
from app.core.scraper_configs import (
    ACQUISITION_GATEWAY_CONFIG,
    DHS_CONFIG,
    DOC_CONFIG,
    DOJ_CONFIG,
    DOS_CONFIG,
    DOT_CONFIG,
    HHS_CONFIG,
    SSA_CONFIG,
    TREASURY_CONFIG,
)
from app.database import db
from app.database.models import DataSource, Prospect
from app.utils.logger import logger

# Map source names to their configurations
SCRAPER_CONFIGS = {
    "Acquisition Gateway": ACQUISITION_GATEWAY_CONFIG,
    "Department of Homeland Security": DHS_CONFIG,
    "Department of Treasury": TREASURY_CONFIG,
    "Department of Transportation": DOT_CONFIG,
    "Health and Human Services": HHS_CONFIG,
    "Social Security Administration": SSA_CONFIG,
    "Department of Commerce": DOC_CONFIG,
    "Department of Justice": DOJ_CONFIG,
    "Department of State": DOS_CONFIG,
}


class DataValidator:
    def __init__(self):
        self.app = create_app()
        self.validation_results = {}

    def get_latest_file_for_source(self, source_name: str) -> Path:
        """Get the most recent data file for a source."""
        config = SCRAPER_CONFIGS.get(source_name)
        if not config:
            logger.error(f"No configuration found for {source_name}")
            return None

        folder_path = Path("data/raw") / config.folder_name
        if not folder_path.exists():
            logger.warning(f"No data folder found for {source_name}")
            return None

        # Find all data files
        files = (
            list(folder_path.glob("*.csv"))
            + list(folder_path.glob("*.xlsx"))
            + list(folder_path.glob("*.xls"))
        )
        if not files:
            logger.warning(f"No data files found for {source_name}")
            return None

        # Get the most recent file
        latest_file = max(files, key=lambda f: f.stat().st_mtime)
        return latest_file

    def read_raw_data(self, file_path: Path, config) -> pd.DataFrame:
        """Read raw data file based on configuration."""
        try:
            if file_path.suffix == ".csv":
                read_options = config.csv_read_options or {}
                df = pd.read_csv(file_path, **read_options)
            elif file_path.suffix in [".xlsx", ".xls"]:
                read_options = config.excel_read_options or {}
                df = pd.read_excel(file_path, **read_options)
            else:
                logger.error(f"Unsupported file type: {file_path.suffix}")
                return None

            logger.info(f"Read {len(df)} rows from {file_path.name}")
            return df
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return None

    def get_database_records(self, source_id: int) -> list[dict]:
        """Get all database records for a source."""
        with self.app.app_context():
            prospects = db.session.query(Prospect).filter_by(source_id=source_id).all()
            return [p.to_dict() for p in prospects]

    def validate_field_mapping(
        self, raw_df: pd.DataFrame, db_records: list[dict], config
    ) -> dict:
        """Validate that fields are correctly mapped from raw data to database."""
        results = {
            "total_raw_records": len(raw_df),
            "total_db_records": len(db_records),
            "field_validations": {},
            "missing_mappings": [],
            "sample_mismatches": [],
        }

        # Check if we have the expected column mappings
        if config.raw_column_rename_map:
            for raw_col, db_col in config.raw_column_rename_map.items():
                if raw_col in raw_df.columns:
                    # Field exists in raw data
                    results["field_validations"][raw_col] = {
                        "maps_to": db_col,
                        "found_in_raw": True,
                        "non_null_count": raw_df[raw_col].notna().sum(),
                        "sample_values": raw_df[raw_col].dropna().head(3).tolist(),
                    }
                else:
                    results["missing_mappings"].append(
                        {
                            "expected_column": raw_col,
                            "maps_to": db_col,
                            "available_columns": list(raw_df.columns)[
                                :10
                            ],  # Show first 10 available
                        }
                    )

        # Sample validation - check first few records
        if db_records and len(raw_df) > 0:
            # Try to match records by native_id if available
            native_id_col = None
            for raw_col, db_col in (config.raw_column_rename_map or {}).items():
                if db_col == "native_id" and raw_col in raw_df.columns:
                    native_id_col = raw_col
                    break

            if native_id_col:
                # Create a mapping of native_ids to db records
                db_by_native_id = {
                    rec["native_id"]: rec for rec in db_records if rec.get("native_id")
                }

                # Check first 5 records
                for idx, row in raw_df.head(5).iterrows():
                    native_id = row.get(native_id_col)
                    if native_id and native_id in db_by_native_id:
                        db_rec = db_by_native_id[native_id]
                        mismatches = []

                        # Check each mapped field
                        for raw_col, db_col in (
                            config.raw_column_rename_map or {}
                        ).items():
                            if raw_col in row and db_col in db_rec:
                                raw_val = row[raw_col]
                                db_val = db_rec[db_col]

                                # Simple comparison (could be enhanced)
                                if pd.notna(raw_val) and db_val is not None:
                                    if str(raw_val).strip() != str(db_val).strip():
                                        mismatches.append(
                                            {
                                                "field": db_col,
                                                "raw_value": str(raw_val)[:100],
                                                "db_value": str(db_val)[:100],
                                            }
                                        )

                        if mismatches:
                            results["sample_mismatches"].append(
                                {"native_id": native_id, "mismatches": mismatches}
                            )

        return results

    def validate_source(self, source_name: str) -> dict:
        """Validate data extraction for a single source."""
        logger.info(f"\nValidating {source_name}...")

        with self.app.app_context():
            # Get source from database
            source = db.session.query(DataSource).filter_by(name=source_name).first()
            if not source:
                return {"error": f"Source {source_name} not found in database"}

            # Get latest raw data file
            latest_file = self.get_latest_file_for_source(source_name)
            if not latest_file:
                return {"error": f"No data files found for {source_name}"}

            # Get configuration
            config = SCRAPER_CONFIGS.get(source_name)
            if not config:
                return {"error": f"No configuration found for {source_name}"}

            # Read raw data
            raw_df = self.read_raw_data(latest_file, config)
            if raw_df is None:
                return {"error": f"Could not read data file for {source_name}"}

            # Get database records
            db_records = self.get_database_records(source.id)

            # Validate field mapping
            validation_results = self.validate_field_mapping(raw_df, db_records, config)
            validation_results["source_name"] = source_name
            validation_results["latest_file"] = str(latest_file)
            validation_results["file_modified"] = datetime.fromtimestamp(
                latest_file.stat().st_mtime
            ).isoformat()

            return validation_results

    def generate_report(self):
        """Generate a comprehensive validation report."""
        report = {
            "validation_timestamp": datetime.now().isoformat(),
            "sources_validated": [],
            "summary": {
                "total_sources": 0,
                "sources_with_data": 0,
                "sources_with_issues": 0,
                "total_raw_records": 0,
                "total_db_records": 0,
            },
        }

        for source_name in SCRAPER_CONFIGS:
            result = self.validate_source(source_name)
            report["sources_validated"].append(result)

            if "error" not in result:
                report["summary"]["sources_with_data"] += 1
                report["summary"]["total_raw_records"] += result.get(
                    "total_raw_records", 0
                )
                report["summary"]["total_db_records"] += result.get(
                    "total_db_records", 0
                )

                if result.get("missing_mappings") or result.get("sample_mismatches"):
                    report["summary"]["sources_with_issues"] += 1

        report["summary"]["total_sources"] = len(SCRAPER_CONFIGS)

        return report

    def print_summary(self, report: dict):
        """Print a human-readable summary of the validation report."""
        print("\n" + "=" * 80)
        print("DATA EXTRACTION VALIDATION REPORT")
        print("=" * 80)
        print(f"Generated: {report['validation_timestamp']}")
        print("\nSummary:")
        print(f"  Total sources: {report['summary']['total_sources']}")
        print(f"  Sources with data: {report['summary']['sources_with_data']}")
        print(f"  Sources with issues: {report['summary']['sources_with_issues']}")
        print(f"  Total raw records: {report['summary']['total_raw_records']:,}")
        print(f"  Total DB records: {report['summary']['total_db_records']:,}")

        print("\n" + "-" * 80)
        print("DETAILED RESULTS BY SOURCE:")
        print("-" * 80)

        for source_result in report["sources_validated"]:
            source_name = source_result.get("source_name", "Unknown")
            print(f"\n{source_name}:")

            if "error" in source_result:
                print(f"  ERROR: {source_result['error']}")
                continue

            print(f"  Latest file: {Path(source_result['latest_file']).name}")
            print(f"  Raw records: {source_result['total_raw_records']:,}")
            print(f"  DB records: {source_result['total_db_records']:,}")

            if source_result.get("missing_mappings"):
                print(
                    f"  ⚠️  Missing mappings: {len(source_result['missing_mappings'])}"
                )
                for missing in source_result["missing_mappings"][:3]:
                    print(
                        f"     - Expected '{missing['expected_column']}' -> '{missing['maps_to']}'"
                    )

            if source_result.get("sample_mismatches"):
                print(
                    f"  ⚠️  Sample mismatches: {len(source_result['sample_mismatches'])}"
                )

            field_count = len(source_result.get("field_validations", {}))
            if field_count > 0:
                print(f"  ✓ Validated fields: {field_count}")


def main():
    """Run the validation."""
    validator = DataValidator()

    logger.info("Starting data extraction validation...")
    report = validator.generate_report()

    # Save detailed report
    report_path = Path("data/validation_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Detailed report saved to: {report_path}")

    # Print summary
    validator.print_summary(report)

    # Return exit code based on issues found
    if report["summary"]["sources_with_issues"] > 0:
        logger.warning("Validation completed with issues found")
        return 1
    logger.success("Validation completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
