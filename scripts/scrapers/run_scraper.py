#!/usr/bin/env python3
"""Run a specific scraper by source name.

Usage:
    python -m scripts.run_scraper --source "DHS"
    python scripts/run_scraper.py --source "DHS"
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.database.models import DataSource
from app.utils.scraper_utils import trigger_scraper


def main():
    parser = argparse.ArgumentParser(description="Run a specific scraper")
    parser.add_argument(
        "--source",
        required=True,
        help="Source name or ID (e.g., 'DHS', 'ACQGW', 'DOJ')",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force run even if recently executed",
    )
    args = parser.parse_args()

    # Create Flask app context
    app = create_app()

    with app.app_context():
        # Try to find the data source
        source = DataSource.query.filter(
            (DataSource.name == args.source)
            | (DataSource.scraper_key == args.source.upper())
        ).first()

        if not source:
            print(f"Error: Data source '{args.source}' not found")
            print("\nAvailable sources:")
            sources = DataSource.query.all()
            for s in sources:
                print(f"  - {s.name} (key: {s.scraper_key})")
            return 1

        print(f"Running scraper for: {source.name} (ID: {source.id})")

        try:
            # Run the scraper
            result = trigger_scraper(source.id)

            if result.get("success"):
                print(f"Successfully triggered scraper for {source.name}")
                if result.get("message"):
                    print(f"Status: {result['message']}")
                return 0
            print(f"Failed to run scraper for {source.name}")
            if result.get("error"):
                print(f"Error: {result['error']}")
            return 1

        except Exception as e:
            print(f"Error running scraper: {e}")
            return 1


if __name__ == "__main__":
    sys.exit(main())
