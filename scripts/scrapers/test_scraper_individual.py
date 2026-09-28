#!/usr/bin/env python3
"""Individual scraper testing script.
Run scrapers independently without web server for testing and debugging.

Usage:
    python test_scraper_individual.py --scraper dhs
    python test_scraper_individual.py --scraper all
    python test_scraper_individual.py --list
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from sqlalchemy import select

from app import create_app

# Import all scrapers
from app.core.scrapers.acquisition_gateway import AcquisitionGatewayScraper
from app.core.scrapers.dhs_scraper import DHSForecastScraper
from app.core.scrapers.doc_scraper import DocScraper
from app.core.scrapers.doj_scraper import DOJForecastScraper
from app.core.scrapers.dos_scraper import DOSForecastScraper
from app.core.scrapers.dot_scraper import DotScraper
from app.core.scrapers.hhs_scraper import HHSForecastScraper
from app.core.scrapers.ssa_scraper import SsaScraper
from app.core.scrapers.treasury_scraper import TreasuryScraper
from app.database import db
from app.database.models import DataSource, Prospect
from app.utils.logger import logger

AVAILABLE_SCRAPERS = {
    "acquisition_gateway": {
        "class": AcquisitionGatewayScraper,
        "name": "Acquisition Gateway",
        "description": "Government-wide procurement forecast",
    },
    "dhs": {
        "class": DHSForecastScraper,
        "name": "Department of Homeland Security",
        "description": "DHS procurement opportunities",
    },
    "treasury": {
        "class": TreasuryScraper,
        "name": "Department of Treasury",
        "description": "Treasury procurement forecast",
    },
    "dot": {
        "class": DotScraper,
        "name": "Department of Transportation",
        "description": "DOT procurement opportunities",
    },
    "hhs": {
        "class": HHSForecastScraper,
        "name": "Health and Human Services",
        "description": "HHS procurement forecast",
    },
    "ssa": {
        "class": SsaScraper,
        "name": "Social Security Administration",
        "description": "SSA contract forecast",
    },
    "doc": {
        "class": DocScraper,
        "name": "Department of Commerce",
        "description": "Commerce procurement forecast",
    },
    "doj": {
        "class": DOJForecastScraper,
        "name": "Department of Justice",
        "description": "DOJ contracting opportunities",
    },
    "dos": {
        "class": DOSForecastScraper,
        "name": "Department of State",
        "description": "State Department procurement forecast",
    },
}


def print_scraper_list():
    """Print list of available scrapers."""
    logger.info("Available scrapers:")
    logger.info("-" * 50)
    for key, info in AVAILABLE_SCRAPERS.items():
        logger.info(f"{key:15} - {info['name']}")
        logger.info(f"{'':15}   {info['description']}")
    logger.info("\nUsage:")
    logger.info("  python test_scraper_individual.py --scraper <scraper_name>")
    logger.info("  python test_scraper_individual.py --scraper all")


async def run_scraper(scraper_key: str, app):
    """Run a single scraper and return results."""
    if scraper_key not in AVAILABLE_SCRAPERS:
        raise ValueError(f"Unknown scraper: {scraper_key}")

    scraper_info = AVAILABLE_SCRAPERS[scraper_key]
    scraper_class = scraper_info["class"]

    logger.info(f"\n{'=' * 60}")
    logger.info(f"Testing: {scraper_info['name']}")
    logger.info(f"Description: {scraper_info['description']}")
    logger.info(f"{'=' * 60}")

    try:
        # Initialize scraper
        logger.info("🔧 Initializing scraper...")
        scraper = scraper_class()
        logger.info(f"✅ Scraper initialized: {scraper.source_name}")
        logger.info(f"   Base URL: {scraper.base_url}")

        # Get count before scraping
        with app.app_context():
            # Find the data source for this scraper
            data_source = db.session.execute(
                select(DataSource).where(DataSource.name == scraper.source_name)
            ).scalar_one_or_none()

            if data_source:
                stmt = select(Prospect).where(Prospect.source_id == data_source.id)
                prospects_before = db.session.execute(stmt).scalars().all()
                count_before = len(prospects_before)
            else:
                prospects_before = []
                count_before = 0
            logger.info(f"📊 Existing records in database: {count_before}")

        # Run scraper
        logger.info("🚀 Starting scraper execution...")
        start_time = asyncio.get_event_loop().time()

        records_loaded = await scraper.scrape()

        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time

        # Get count after scraping
        with app.app_context():
            if data_source:
                stmt = select(Prospect).where(Prospect.source_id == data_source.id)
                prospects_after = db.session.execute(stmt).scalars().all()
                count_after = len(prospects_after)
            else:
                # Try to find data source again in case it was created during scraping
                data_source = db.session.execute(
                    select(DataSource).where(DataSource.name == scraper.source_name)
                ).scalar_one_or_none()
                if data_source:
                    stmt = select(Prospect).where(Prospect.source_id == data_source.id)
                    prospects_after = db.session.execute(stmt).scalars().all()
                    count_after = len(prospects_after)
                else:
                    prospects_after = []
                    count_after = 0

        # Print results
        logger.info("\n📈 RESULTS:")
        logger.info(f"   Records loaded this run: {records_loaded}")
        logger.info(f"   Total records in DB: {count_after}")
        logger.info(f"   New records added: {count_after - count_before}")
        print(f"   Execution time: {duration:.2f} seconds")

        if records_loaded > 0:
            print("✅ SUCCESS: Scraper completed with data")

            # Show sample records
            if count_after > 0:
                print(f"\n📋 Sample records (showing last {min(3, count_after)}):")
                recent_prospects = prospects_after[-3:]
                for i, prospect in enumerate(recent_prospects, 1):
                    # Handle None values gracefully
                    native_id = prospect.native_id if prospect.native_id else "NO_ID"
                    title = prospect.title[:50] if prospect.title else "NO_TITLE"
                    agency = prospect.agency if prospect.agency else "NO_AGENCY"

                    print(f"   {i}. {native_id} - {title}...")
                    print(f"      Agency: {agency}")
                    print(f"      Loaded: {prospect.loaded_at}")
        else:
            print("⚠️  WARNING: Scraper completed but no records were loaded")
            print("   This could indicate:")
            print("   - Empty data source")
            print("   - Scraping error")
            print("   - Website structure changes")

        return {
            "success": True,
            "records_loaded": records_loaded,
            "total_records": count_after,
            "duration": duration,
            "error": None,
        }

    except Exception as e:
        logger.error("❌ ERROR: Scraper failed with exception:")
        logger.error(f"   {type(e).__name__}: {str(e)}")
        import traceback

        logger.error("\n🔍 Full traceback:")
        traceback.print_exc()

        return {
            "success": False,
            "records_loaded": 0,
            "total_records": 0,
            "duration": 0,
            "error": str(e),
        }


async def run_all_scrapers(app):
    """Run all scrapers and summarize results."""
    logger.info(f"\n{'=' * 60}")
    logger.info("RUNNING ALL SCRAPERS")
    logger.info(f"{'=' * 60}")

    results = {}
    total_start_time = asyncio.get_event_loop().time()

    for scraper_key in AVAILABLE_SCRAPERS:
        results[scraper_key] = await run_scraper(scraper_key, app)

        # Brief pause between scrapers
        logger.info("⏸️  Pausing 2 seconds between scrapers...")
        await asyncio.sleep(2)

    total_end_time = asyncio.get_event_loop().time()
    total_duration = total_end_time - total_start_time

    # Summary report
    logger.info(f"\n{'=' * 60}")
    logger.info("SUMMARY REPORT")
    logger.info(f"{'=' * 60}")

    successful_scrapers = []
    failed_scrapers = []
    total_records = 0

    for scraper_key, result in results.items():
        scraper_name = AVAILABLE_SCRAPERS[scraper_key]["name"]

        if result["success"]:
            successful_scrapers.append(scraper_key)
            total_records += result["records_loaded"]
            status = "✅ SUCCESS"
        else:
            failed_scrapers.append(scraper_key)
            status = "❌ FAILED"

        logger.info(
            f"{scraper_key:15} {status:10} {result['records_loaded']:>6} records  {result['duration']:>6.1f}s"
        )

    logger.info("\n📊 OVERALL STATISTICS:")
    logger.info(f"   Total scrapers: {len(AVAILABLE_SCRAPERS)}")
    logger.info(f"   Successful: {len(successful_scrapers)}")
    logger.info(f"   Failed: {len(failed_scrapers)}")
    logger.info(f"   Total records loaded: {total_records}")
    logger.info(f"   Total execution time: {total_duration:.2f} seconds")

    if failed_scrapers:
        logger.error("\n❌ FAILED SCRAPERS:")
        for scraper_key in failed_scrapers:
            error = results[scraper_key]["error"]
            logger.error(f"   {scraper_key}: {error}")

    return results


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Test individual consolidated scrapers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_scraper_individual.py --list
  python test_scraper_individual.py --scraper dhs
  python test_scraper_individual.py --scraper acquisition_gateway
  python test_scraper_individual.py --scraper all
        """,
    )

    parser.add_argument(
        "--scraper",
        help='Scraper to run (or "all" for all scrapers)',
        choices=list(AVAILABLE_SCRAPERS.keys()) + ["all"],
    )

    parser.add_argument("--list", action="store_true", help="List available scrapers")

    args = parser.parse_args()

    if args.list:
        print_scraper_list()
        return

    if not args.scraper:
        parser.print_help()
        return

    # Create Flask app (needed for database context, not running web server)
    logger.info("🔧 Initializing Flask application...")
    logger.info(
        "   Note: This creates database context only - no web server is started"
    )
    app = create_app()

    with app.app_context():
        # Ensure database is set up
        db.create_all()
        logger.info("✅ Database initialized")

        # Run scraper(s)
        if args.scraper == "all":
            asyncio.run(run_all_scrapers(app))
        else:
            asyncio.run(run_scraper(args.scraper, app))


if __name__ == "__main__":
    main()
