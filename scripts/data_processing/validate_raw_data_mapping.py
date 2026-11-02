#!/usr/bin/env python3
"""Raw Data Mapping Validation
Checks raw data files against scraper configurations to verify field mappings.
This version doesn't require database access.
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


def get_latest_file_for_source(config) -> Path:
    """Get the most recent data file for a source."""
    folder_path = Path("data/raw") / config.folder_name
    if not folder_path.exists():
        return None

    # Find all data files - including .xlsm for SSA
    files = (
        list(folder_path.glob("*.csv"))
        + list(folder_path.glob("*.xlsx"))
        + list(folder_path.glob("*.xls"))
        + list(folder_path.glob("*.xlsm"))
    )
    if not files:
        return None

    # Get the most recent file
    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    return latest_file


def read_raw_data(file_path: Path, config) -> pd.DataFrame:
    """Read raw data file based on configuration."""
    try:
        if file_path.suffix == ".csv":
            # Try different encoding and options for problematic CSVs
            read_options = config.csv_read_options or {}
            # Add common fixes for CSV issues
            read_options.setdefault("on_bad_lines", "skip")
            read_options.setdefault("encoding", "utf-8")
            read_options.setdefault("engine", "python")

            try:
                df = pd.read_csv(file_path, **read_options)
            except:
                # Try with quoting if first attempt fails
                read_options["quoting"] = 1  # QUOTE_ALL
                df = pd.read_csv(file_path, **read_options)

        elif file_path.suffix in [".xlsx", ".xls", ".xlsm"]:
            read_options = config.excel_read_options or {}
            # Handle Treasury's HTML files with .xls extension
            if config.file_read_strategy == "html" or file_path.parent.name == "treas":
                # Treasury files are actually HTML with unusual structure
                try:
                    # Read all tables from HTML - Treasury uses header_rows in a special way
                    tables = pd.read_html(str(file_path), header=0)
                    if tables and len(tables) > 0:
                        df = tables[0]
                        # Treasury HTML has multi-level headers that pandas reads as tuples
                        # We need to clean up the column names
                        if isinstance(df.columns[0], tuple):
                            # Extract the first element of each tuple for column names
                            df.columns = [
                                col[0] if isinstance(col, tuple) else col
                                for col in df.columns
                            ]
                        print(
                            f"Successfully read Treasury HTML table with {len(df)} rows, {len(df.columns)} columns"
                        )
                    else:
                        print("No tables found in Treasury HTML file")
                        return None
                except Exception as html_error:
                    print(f"HTML parsing failed: {html_error}")
                    # Fallback to Excel if HTML fails
                    if file_path.suffix == ".xls":
                        read_options["engine"] = "xlrd"
                    df = pd.read_excel(file_path, **read_options)
            else:
                # Regular Excel files (including .xlsm)
                if file_path.suffix == ".xls":
                    read_options["engine"] = "xlrd"
                elif file_path.suffix == ".xlsm":
                    # Use openpyxl for .xlsm files (Excel with macros)
                    read_options["engine"] = "openpyxl"
                df = pd.read_excel(file_path, **read_options)
        else:
            print(f"Unsupported file type: {file_path.suffix}")
            return None

        return df
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None


def validate_mapping(source_name: str, config) -> dict:
    """Validate field mapping for a source."""
    result = {
        "source_name": source_name,
        "status": "unknown",
        "file_found": False,
        "mappings_found": 0,
        "mappings_missing": 0,
        "sample_data": {},
        "issues": [],
    }

    # Get latest file
    latest_file = get_latest_file_for_source(config)
    if not latest_file:
        result["status"] = "no_data"
        result["issues"].append("No data files found")
        return result

    result["file_found"] = True
    result["file_path"] = str(latest_file.name)
    result["file_date"] = datetime.fromtimestamp(latest_file.stat().st_mtime).strftime(
        "%Y-%m-%d %H:%M"
    )

    # Read data
    df = read_raw_data(latest_file, config)
    if df is None:
        result["status"] = "read_error"
        result["issues"].append("Could not read data file")
        return result

    result["total_rows"] = len(df)
    result["total_columns"] = len(df.columns)

    # Check mappings
    if config.raw_column_rename_map:
        for raw_col, db_col in config.raw_column_rename_map.items():
            if raw_col in df.columns:
                result["mappings_found"] += 1
                # Get sample data
                non_null_values = df[raw_col].dropna()
                if len(non_null_values) > 0:
                    # Convert values to strings to avoid JSON serialization issues
                    sample_values = []
                    for val in non_null_values.head(3):
                        if pd.isna(val):
                            sample_values.append(None)
                        else:
                            sample_values.append(str(val))

                    result["sample_data"][raw_col] = {
                        "maps_to": db_col,
                        "non_null_count": len(non_null_values),
                        "null_count": len(df) - len(non_null_values),
                        "sample_values": sample_values,
                    }
            else:
                result["mappings_missing"] += 1
                result["issues"].append(f"Expected column '{raw_col}' not found")

    # Show available columns not in mapping
    mapped_columns = (
        set(config.raw_column_rename_map.keys())
        if config.raw_column_rename_map
        else set()
    )
    unmapped_columns = [col for col in df.columns if col not in mapped_columns]
    if unmapped_columns:
        result["unmapped_columns"] = unmapped_columns[:10]  # First 10

    # Determine overall status
    if result["mappings_missing"] == 0 and result["mappings_found"] > 0:
        result["status"] = "success"
    elif result["mappings_found"] > 0:
        result["status"] = "partial"
    else:
        result["status"] = "failed"

    return result


def print_validation_report(results: list[dict]):
    """Print a formatted validation report."""
    print("\n" + "=" * 80)
    print("RAW DATA MAPPING VALIDATION REPORT")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Summary
    success_count = sum(1 for r in results if r["status"] == "success")
    partial_count = sum(1 for r in results if r["status"] == "partial")
    failed_count = sum(1 for r in results if r["status"] == "failed")
    no_data_count = sum(1 for r in results if r["status"] == "no_data")

    print("SUMMARY:")
    print(f"  Total sources: {len(results)}")
    print(f"  ✅ Success: {success_count}")
    print(f"  ⚠️  Partial: {partial_count}")
    print(f"  ❌ Failed: {failed_count}")
    print(f"  📁 No data: {no_data_count}")

    print("\n" + "-" * 80)
    print("DETAILED RESULTS:")
    print("-" * 80)

    for result in results:
        status_icon = {
            "success": "✅",
            "partial": "⚠️",
            "failed": "❌",
            "no_data": "📁",
            "read_error": "🚫",
        }.get(result["status"], "❓")

        print(f"\n{status_icon} {result['source_name']}:")

        if result["file_found"]:
            print(f"   File: {result['file_path']} (modified: {result['file_date']})")
            print(f"   Rows: {result.get('total_rows', 'N/A'):,}")
            print(f"   Columns: {result.get('total_columns', 'N/A')}")
            print(
                f"   Mappings: {result.get('mappings_found', 0)} found, {result.get('mappings_missing', 0)} missing"
            )

            if result.get("sample_data"):
                print("   Sample mapped fields:")
                for raw_col, info in list(result["sample_data"].items())[:3]:
                    print(f"     • '{raw_col}' → '{info['maps_to']}'")
                    print(
                        f"       Non-null: {info['non_null_count']:,} ({info['non_null_count'] / result['total_rows'] * 100:.1f}%)"
                    )
                    if info["sample_values"]:
                        sample = str(info["sample_values"][0])[:50]
                        if len(sample) == 50:
                            sample += "..."
                        print(f"       Sample: {sample}")

            if result.get("unmapped_columns"):
                print(f"   Unmapped columns ({len(result['unmapped_columns'])} shown):")
                for col in result["unmapped_columns"][:5]:
                    print(f"     - {col}")

        if result.get("issues"):
            print("   Issues:")
            for issue in result["issues"]:
                print(f"     ⚠️  {issue}")


def main():
    """Run the validation."""
    print("Validating raw data mappings...")

    results = []
    for source_name, config in SCRAPER_CONFIGS.items():
        result = validate_mapping(source_name, config)
        results.append(result)

    # Save detailed results
    output_path = Path("data/raw_data_validation.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to: {output_path}")

    # Print report
    print_validation_report(results)

    # Return success if all sources have at least partial success
    failed_sources = [r for r in results if r["status"] in ["failed", "read_error"]]
    if failed_sources:
        print(f"\n❌ Validation failed for {len(failed_sources)} sources")
        return 1
    print("\n✅ Validation completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
