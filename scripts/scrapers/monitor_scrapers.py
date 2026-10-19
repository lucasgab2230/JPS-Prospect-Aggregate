#!/usr/bin/env python3
"""Monitor scrapers properly by waiting for completion."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from app.database.models import DataSource, ScraperStatus
from app.utils.scraper_utils import trigger_scraper


def monitor_scraper(source_id, source_name, timeout=300):
    """Monitor a scraper until completion or timeout."""
    print(f"\n{'=' * 60}")
    print(f"Starting {source_name} (ID: {source_id})")
    print(f"{'=' * 60}")

    # Trigger the scraper
    try:
        result = trigger_scraper(source_id)
        print(f"✓ Scraper started: {result['message']}")
    except Exception as e:
        print(f"✗ Failed to start: {e}")
        return False

    # Monitor until completion
    start_time = time.time()
    last_status = None

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            print(f"✗ Timeout after {timeout} seconds")
            return False

        # Check status
        status = ScraperStatus.query.filter_by(source_id=source_id).first()
        if status:
            if status.status != last_status:
                print(f"  Status: {status.status} - {status.details}")
                last_status = status.status

            if status.status in ["completed", "failed"]:
                print(
                    f"\n{'✓' if status.status == 'completed' else '✗'} {source_name} {status.status}: {status.details}"
                )
                print(f"  Duration: {elapsed:.1f} seconds")
                return status.status == "completed"

        time.sleep(2)


def main():
    app = create_app()
    with app.app_context():
        # Get all data sources with scrapers
        sources = (
            DataSource.query.filter(DataSource.scraper_key.isnot(None))
            .order_by(DataSource.id)
            .all()
        )

        print(f"Found {len(sources)} scrapers to run\n")

        success_count = 0
        for source in sources:
            if monitor_scraper(source.id, source.name):
                success_count += 1

            # Small delay between scrapers
            time.sleep(2)

        print(f"\n{'=' * 60}")
        print(
            f"Summary: {success_count}/{len(sources)} scrapers completed successfully"
        )
        print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
