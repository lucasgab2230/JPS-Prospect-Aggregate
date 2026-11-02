#!/usr/bin/env python3
"""NAICS Code Standardization Migration Script

This script standardizes NAICS codes in the database to ensure consistent formatting:
- Separates combined NAICS codes and descriptions into separate fields
- Standardizes display format to "334516 | Description"
- Preserves original data integrity while improving consistency

Usage:
    python scripts/migrations/standardize_naics_formatting.py --preview    # Preview changes
    python scripts/migrations/standardize_naics_formatting.py --execute    # Execute changes
"""

import argparse
import os
import re
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from flask import Flask

from app.database import db
from app.database.models import Prospect
from app.services.llm_service import LLMService
from app.utils.logger import logger


class NAICSStandardizationMigration:
    """Handles standardization of NAICS codes in the database"""

    def __init__(self):
        self.llm_service = LLMService()
        self.stats = {
            "total_prospects": 0,
            "prospects_with_naics": 0,
            "standardized_count": 0,
            "separated_combined_formats": 0,
            "preserved_existing_separate": 0,
            "errors": 0,
            "changes": [],
        }

    def parse_naics_with_standardizer(self, naics_value: str) -> dict[str, str | None]:
        """Use the updated LLM service parser for consistency"""
        return self.llm_service.parse_existing_naics(naics_value)

    def analyze_current_naics_data(self) -> dict[str, any]:
        """Analyze current NAICS data patterns in the database"""
        prospects = Prospect.query.filter(Prospect.naics.isnot(None)).all()

        analysis = {
            "total_with_naics": len(prospects),
            "format_patterns": {},
            "separate_fields_count": 0,
            "combined_formats_count": 0,
            "examples": [],
        }

        for prospect in prospects:
            naics = prospect.naics.strip() if prospect.naics else ""
            naics_desc = (
                prospect.naics_description.strip() if prospect.naics_description else ""
            )

            # Check if both fields are populated (ideal state)
            if naics and naics_desc:
                analysis["separate_fields_count"] += 1
                continue

            # Check for combined formats in naics field
            if naics:
                parsed = self.parse_naics_with_standardizer(naics)
                original_format = parsed.get("original_format", "unknown")

                if original_format != "code_only":
                    analysis["combined_formats_count"] += 1

                    # Track format patterns
                    if original_format not in analysis["format_patterns"]:
                        analysis["format_patterns"][original_format] = 0
                    analysis["format_patterns"][original_format] += 1

                    # Store examples
                    if len(analysis["examples"]) < 20:
                        analysis["examples"].append(
                            {
                                "prospect_id": prospect.id[:8] + "...",
                                "original_naics": naics,
                                "format": original_format,
                                "parsed_code": parsed["code"],
                                "parsed_description": parsed["description"],
                            }
                        )

        return analysis

    def standardize_prospect_naics(
        self, prospect: Prospect, preview_mode: bool = True
    ) -> dict[str, any]:
        """Standardize NAICS for a single prospect"""
        changes = {
            "prospect_id": prospect.id,
            "original_naics": prospect.naics,
            "original_description": prospect.naics_description,
            "new_naics": None,
            "new_description": None,
            "action": "no_change",
            "reasoning": "",
        }

        # Skip if no NAICS data
        if not prospect.naics:
            changes["reasoning"] = "No NAICS data present"
            return changes

        naics = prospect.naics.strip()
        naics_desc = (
            prospect.naics_description.strip() if prospect.naics_description else ""
        )

        # If both fields are properly populated with just code in naics field, no change needed
        if re.match(r"^\d{6}$", naics) and naics_desc:
            changes["reasoning"] = "Already properly separated"
            self.stats["preserved_existing_separate"] += 1
            return changes

        # Parse the naics field to see if it contains combined data
        parsed = self.parse_naics_with_standardizer(naics)

        if not parsed["code"]:
            changes["reasoning"] = "Could not parse NAICS code"
            self.stats["errors"] += 1
            return changes

        # Determine if we need to update
        needs_update = False
        new_naics = parsed["code"]
        new_description = parsed["description"]

        # Case 1: NAICS field contains combined format
        if parsed["original_format"] != "code_only":
            needs_update = True
            changes["action"] = "separate_combined"
            changes["reasoning"] = (
                f"Separated combined format ({parsed['original_format']})"
            )
            self.stats["separated_combined_formats"] += 1

        # Case 2: Description field is empty but we parsed one
        elif not naics_desc and new_description:
            needs_update = True
            changes["action"] = "add_description"
            changes["reasoning"] = "Added missing description from parsed data"

        if needs_update:
            changes["new_naics"] = new_naics
            changes["new_description"] = new_description

            if not preview_mode:
                # Update the prospect
                prospect.naics = new_naics
                prospect.naics_description = new_description
                # Preserve existing source or set to 'standardized' if unknown
                if not prospect.naics_source:
                    prospect.naics_source = "standardized"

            self.stats["standardized_count"] += 1

        return changes

    def run_migration(
        self, preview_mode: bool = True, limit: int | None = None
    ) -> dict[str, any]:
        """Run the NAICS standardization migration"""
        logger.info(
            f"Starting NAICS standardization {'(PREVIEW MODE)' if preview_mode else '(EXECUTION MODE)'}"
        )

        # Get all prospects with NAICS data
        query = Prospect.query.filter(Prospect.naics.isnot(None))
        if limit:
            query = query.limit(limit)

        prospects = query.all()
        self.stats["total_prospects"] = len(prospects)

        logger.info(f"Found {len(prospects)} prospects with NAICS data to process")

        # Process each prospect
        for i, prospect in enumerate(prospects, 1):
            if i % 100 == 0:
                logger.info(f"Processed {i}/{len(prospects)} prospects...")

            try:
                changes = self.standardize_prospect_naics(prospect, preview_mode)
                if changes["action"] != "no_change":
                    self.stats["changes"].append(changes)

            except Exception as e:
                logger.error(f"Error processing prospect {prospect.id}: {str(e)}")
                self.stats["errors"] += 1

        # Commit changes if not in preview mode
        if not preview_mode:
            try:
                db.session.commit()
                logger.info("Successfully committed all changes to database")
            except Exception as e:
                logger.error(f"Failed to commit changes: {str(e)}")
                db.session.rollback()
                raise

        return self.stats

    def print_analysis_report(self, analysis: dict[str, any]):
        """Print analysis report of current NAICS data"""
        print("\n" + "=" * 60)
        print("NAICS DATA ANALYSIS REPORT")
        print("=" * 60)
        print(f"Total prospects with NAICS data: {analysis['total_with_naics']}")
        print(
            f"Already properly separated (code + description): {analysis['separate_fields_count']}"
        )
        print(
            f"Combined formats needing separation: {analysis['combined_formats_count']}"
        )

        if analysis["format_patterns"]:
            print("\nFormat patterns found:")
            for format_type, count in analysis["format_patterns"].items():
                print(f"  {format_type}: {count} prospects")

        if analysis["examples"]:
            print(f"\nFirst {len(analysis['examples'])} examples of combined formats:")
            for example in analysis["examples"][:10]:
                print(
                    f"  {example['prospect_id']} | {example['format']} | '{example['original_naics']}'"
                )
                print(
                    f"    → Code: {example['parsed_code']}, Description: {example['parsed_description']}"
                )

    def print_migration_report(self, stats: dict[str, any], preview_mode: bool):
        """Print migration results report"""
        print("\n" + "=" * 60)
        print(
            f"NAICS STANDARDIZATION {'PREVIEW' if preview_mode else 'EXECUTION'} REPORT"
        )
        print("=" * 60)
        print(f"Total prospects processed: {stats['total_prospects']}")
        print(f"Prospects standardized: {stats['standardized_count']}")
        print(f"Combined formats separated: {stats['separated_combined_formats']}")
        print(
            f"Existing separate fields preserved: {stats['preserved_existing_separate']}"
        )
        print(f"Errors encountered: {stats['errors']}")

        if stats["changes"]:
            print("\nFirst 10 changes made:")
            for change in stats["changes"][:10]:
                print(
                    f"  {change['prospect_id'][:8]}... | {change['action']} | {change['reasoning']}"
                )
                if change["action"] != "no_change":
                    print(
                        f"    Before: '{change['original_naics']}' + '{change['original_description'] or 'None'}'"
                    )
                    print(
                        f"    After:  '{change['new_naics']}' + '{change['new_description'] or 'None'}'"
                    )


def create_app():
    """Create Flask app with database context"""
    app = Flask(__name__)

    # Load configuration
    from app.config import active_config

    app.config.from_object(active_config)

    # Initialize database
    db.init_app(app)

    return app


def main():
    parser = argparse.ArgumentParser(
        description="Standardize NAICS code formatting in database"
    )
    parser.add_argument(
        "--preview", action="store_true", help="Preview changes without executing"
    )
    parser.add_argument(
        "--execute", action="store_true", help="Execute changes to database"
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Only analyze current data without changes",
    )
    parser.add_argument(
        "--limit", type=int, help="Limit number of prospects to process (for testing)"
    )

    args = parser.parse_args()

    if not any([args.preview, args.execute, args.analyze]):
        print("Error: Must specify --preview, --execute, or --analyze")
        parser.print_help()
        sys.exit(1)

    if args.execute and args.preview:
        print("Error: Cannot specify both --execute and --preview")
        sys.exit(1)

    app = create_app()

    with app.app_context():
        migration = NAICSStandardizationMigration()

        if args.analyze:
            # Just run analysis
            analysis = migration.analyze_current_naics_data()
            migration.print_analysis_report(analysis)
        else:
            # Run migration
            preview_mode = args.preview or not args.execute

            if not preview_mode:
                # Confirm execution
                response = input(
                    "Are you sure you want to execute changes to the database? (yes/no): "
                )
                if response.lower() != "yes":
                    print("Migration cancelled.")
                    sys.exit(0)

            # Run analysis first
            print("Analyzing current NAICS data...")
            analysis = migration.analyze_current_naics_data()
            migration.print_analysis_report(analysis)

            # Run migration
            stats = migration.run_migration(preview_mode, args.limit)
            migration.print_migration_report(stats, preview_mode)

            if preview_mode:
                print("\nTo execute these changes, run:")
                print(f"python {sys.argv[0]} --execute")


if __name__ == "__main__":
    main()
