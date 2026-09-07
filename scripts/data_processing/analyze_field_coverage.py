#!/usr/bin/env python3
"""Analyze field coverage across sample source files and validate mapping normalization.

Usage:
  python scripts/analyze_field_coverage.py \
    --fixtures tests/fixtures/golden_files \
    [--min-threshold 0.8]

This is standalone and does not import the app codebase to avoid heavy deps.
It replicates the normalization strategy to assess presence/inferability.
"""

import argparse
import os
import sys

import pandas as pd

STANDARD_FIELDS = [
    "title",
    "description",
    "agency",
    "native_id",
    "naics",
    "estimated_value_text",
    "set_aside",
    "release_date_raw",
    "award_date_raw",
    "award_fiscal_year",
    "primary_contact_name",
    "primary_contact_email",
    "place_city",
    "place_state",
    "place_country",
]


# Candidate source headers per standardized field (used for pre-normalization coverage)
CANDIDATES: dict[str, list[str]] = {
    "title": ["Title", "Contract Name", "Project Title", "Requirement Title"],
    "description": [
        "Description",
        "Description of Requirement",
        "Requirement Description",
        "Body",
        "PSC",
    ],
    "agency": [
        "Agency",
        "Component",
        "Bureau",
        "Operating Division",
        "Office Symbol",
        "Organization",
        "Procurement Office",
    ],
    "native_id": [
        "Listing ID",
        "APFS Number",
        "Forecast ID",
        "Action Tracking Number",
        "Contract Number",
        "Sequence Number",
        "Procurement Number",
        "APP #",
        "Specific Id",
    ],
    "naics": ["NAICS", "NAICS Code", "Primary NAICS"],
    "estimated_value_text": [
        "Estimated Contract Value",
        "Estimated Total Contract Value",
        "Estimated Value Range",
        "Estimated Value",
        "ESTIMATED VALUE",
        "Dollar Range",
        "EST COST PER FY",
    ],
    "set_aside": [
        "Set Aside Type",
        "Small Business Set-Aside",
        "Type Of Awardee",
        "Small Business Approach",
        "Type of Small Business Set-aside",
        "TYPE OF COMPETITION",
        "Competition Type",
        "Anticipated Set Aside",
        "Anticipated Set Aside And Type",
    ],
    "release_date_raw": [
        "Estimated Solicitation Date",
        "Target Solicitation Date",
        "Anticipated Solicitation Release Date",
        "Target Solicitation Month/Year",
    ],
    "award_date_raw": [
        "Ultimate Completion Date",
        "Target Award Date",
        "Anticipated Award Date",
    ],
    "award_fiscal_year": ["Estimated Award FY", "AWARD FISCAL YEAR"],
    "primary_contact_email": [
        "Point of Contact (Email)",
        "Program Office POC Email",
        "DOJ Requirement POC - Email Address",
        "DOJ Small Business POC - Email Address",
    ],
    "primary_contact_name": [
        "Content: Point of Contact (Name) For",
        "Point Of Contact Name",
        "Program Office POC Name",
        "Program Office POC First Name",
        "Program Office POC Last Name",
    ],
    # Place fields: recognize combined or split
    "place_city": [
        "Place of Performance City",
        "Place Of Performance City",
        "PLACE OF PERFORMANCE",
        "Place of Performance",
    ],
    "place_state": [
        "Place of Performance State",
        "Place Of Performance State",
        "PLACE OF PERFORMANCE",
        "Place of Performance",
    ],
    "place_country": [
        "Place of Performance Country",
        "Place Of Performance Country",
        "Country",
    ],
}


def read_table(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[1].lower()
    if ext in [".csv"]:
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.read_csv(
                path, engine="python", on_bad_lines="skip", skip_blank_lines=True
            )
    if ext in [".xlsx", ".xls", ".xlsm"]:
        try:
            return pd.read_excel(path)
        except Exception:
            return pd.read_excel(path, engine="openpyxl")
    if ext in [".html", ".htm"]:
        tables = pd.read_html(path)
        return tables[0] if tables else pd.DataFrame()
    # Fallback: try CSV then Excel
    try:
        return pd.read_csv(path)
    except Exception:
        try:
            return pd.read_excel(path)
        except Exception:
            return pd.DataFrame()


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    # Helper similar to base normalization
    def has_nonempty(col: str) -> bool:
        return (
            col in df.columns
            and df[col].notna().any()
            and df[col].astype(str).str.strip().ne("").any()
        )

    def ensure_col(col: str):
        if col not in df.columns:
            df[col] = None

    def fill_first_available(target: str, candidates: list[str]):
        ensure_col(target)
        if has_nonempty(target):
            return
        for cand in candidates:
            if cand in df.columns and has_nonempty(cand):
                mask = df[target].isna() | df[target].astype(str).str.strip().eq("")
                df.loc[mask, target] = df.loc[mask, cand]
                break

    for field in [
        "title",
        "description",
        "agency",
        "native_id",
        "naics",
        "estimated_value_text",
        "set_aside",
        "release_date_raw",
        "award_date_raw",
        "award_fiscal_year",
        "primary_contact_email",
        "primary_contact_name",
    ]:
        fill_first_available(field, CANDIDATES.get(field, []))

    # Primary contact name from first/last name if present
    if not has_nonempty("primary_contact_name"):
        first_variants = ["Program Office POC First Name", "Primary Contact First Name"]
        last_variants = ["Program Office POC Last Name", "Primary Contact Last Name"]
        first = next((c for c in first_variants if c in df.columns), None)
        last = next((c for c in last_variants if c in df.columns), None)
        if first and last:
            combined = (df[first].fillna("") + " " + df[last].fillna("")).str.strip()
            df["primary_contact_name"] = combined.where(combined != "", None)

    # Place handling
    # Combined to place_raw if present
    if "place_raw" not in df.columns:
        for cand in [
            "Place of Performance",
            "PLACE OF PERFORMANCE",
            "Place Of Performance",
        ]:
            if cand in df.columns:
                df["place_raw"] = df[cand]
                break

    # Split city/state from place_raw if needed
    if "place_raw" in df.columns:
        extracted = (
            df["place_raw"].astype(str).str.extract(r"^([^,]+)(?:,\s*([A-Z]{2}))?$")
        )
        ensure_col("place_city")
        ensure_col("place_state")
        df.loc[df["place_city"].isna(), "place_city"] = extracted[0]
        df.loc[df["place_state"].isna(), "place_state"] = extracted[1]

    if "place_country" not in df.columns:
        if "place_country_raw" in df.columns:
            df["place_country"] = df["place_country_raw"].fillna("USA")
        elif "Country" in df.columns:
            df["place_country"] = df["Country"].fillna("USA")
        else:
            df["place_country"] = "USA"

    return df


def analyze(fixtures_root: str, min_threshold: float) -> int:
    sources: list[tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(fixtures_root):
        # Only deepest source dirs
        for fname in filenames:
            if fname.lower().endswith((".csv", ".xlsx", ".xls", ".html", ".htm")):
                sources.append(
                    (os.path.basename(dirpath), os.path.join(dirpath, fname))
                )
                break

    if not sources:
        print(f"No fixture files found under {fixtures_root}")
        return 1

    total = len(sources)
    coverage_after = dict.fromkeys(STANDARD_FIELDS, 0)
    coverage_before = dict.fromkeys(STANDARD_FIELDS, 0)

    def present_after(df: pd.DataFrame, field: str) -> bool:
        return field in df.columns and df[field].notna().any()

    def present_before(df: pd.DataFrame, field: str) -> bool:
        # Any candidate header present before normalization
        for cand in CANDIDATES.get(field, []):
            if cand in df.columns:
                return True
        return False

    missing_by_field = {f: [] for f in STANDARD_FIELDS}

    for src_name, path in sources:
        try:
            df = read_table(path)
            if df is None or df.empty:
                print(f"WARN: Empty or unreadable file for {src_name}: {path}")
                for f in STANDARD_FIELDS:
                    missing_by_field[f].append(src_name)
                continue

            # Before normalization
            for f in STANDARD_FIELDS:
                if present_before(df, f):
                    coverage_before[f] += 1

            # After normalization
            norm = normalize(df.copy())
            for f in STANDARD_FIELDS:
                if present_after(norm, f):
                    coverage_after[f] += 1
                else:
                    missing_by_field[f].append(src_name)
        except Exception as e:
            print(f"ERROR processing {src_name} ({path}): {e}")
            for f in STANDARD_FIELDS:
                missing_by_field[f].append(src_name)

    print("\nField coverage across sources (after normalization):")
    promotable: list[str] = []
    for f in STANDARD_FIELDS:
        pct = coverage_after[f] / total
        print(f"- {f}: {coverage_after[f]}/{total} ({pct:.0%})")
        if pct >= min_threshold:
            promotable.append(f)

    print(f"\nFields meeting threshold (>= {min_threshold:.0%}):")
    if promotable:
        print("  " + ", ".join(promotable))
    else:
        print("  None")

    print("\nGaps by field (after normalization):")
    for f in STANDARD_FIELDS:
        if missing_by_field[f]:
            print(
                f"- {f}: missing in {len(missing_by_field[f])}/{total} -> {sorted(set(missing_by_field[f]))}"
            )

    print("\nPre-normalization candidate header presence:")
    for f in STANDARD_FIELDS:
        pct = coverage_before[f] / total
        print(f"- {f}: {coverage_before[f]}/{total} ({pct:.0%})")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Analyze field coverage across sources"
    )
    parser.add_argument(
        "--fixtures", default="tests/fixtures/golden_files", help="Root of fixtures"
    )
    parser.add_argument(
        "--min-threshold", type=float, default=0.8, help="Promotion threshold (0-1)"
    )
    args = parser.parse_args()

    if not os.path.isdir(args.fixtures):
        print(f"Fixtures directory not found: {args.fixtures}")
        sys.exit(1)

    rc = analyze(args.fixtures, args.min_threshold)
    sys.exit(rc)


if __name__ == "__main__":
    main()
