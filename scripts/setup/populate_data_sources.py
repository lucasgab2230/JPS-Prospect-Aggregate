#!/usr/bin/env python3
"""Script to populate initial data sources"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.database import db
from app.database.models import DataSource, ScraperStatus
from app.utils.ensure_data_sources import ALL_DATA_SOURCES
from app.utils.logger import logger

# Use the centralized data source list
DATA_SOURCES = ALL_DATA_SOURCES


def populate_data_sources():
    """Populate initial data sources if they don't exist"""
    app = create_app()

    with app.app_context():
        try:
            added_count = 0

            for source_data in DATA_SOURCES:
                # Check if source already exists
                existing = DataSource.query.filter_by(name=source_data["name"]).first()
                if existing:
                    # Update scraper_key if missing
                    if not existing.scraper_key:
                        existing.scraper_key = source_data["scraper_key"]
                        db.session.commit()
                        logger.info(f"Updated scraper_key for {source_data['name']}")
                    else:
                        logger.info(f"Data source {source_data['name']} already exists")
                    continue

                # Create new data source
                new_source = DataSource(
                    name=source_data["name"],
                    scraper_key=source_data["scraper_key"],
                    url=source_data["url"],
                    description=source_data["description"],
                    frequency=source_data["frequency"],
                )
                db.session.add(new_source)
                db.session.flush()  # Get the ID

                # Create initial status
                initial_status = ScraperStatus(
                    source_id=new_source.id,
                    status="pending",
                    details="Newly created data source, awaiting first scrape.",
                )
                db.session.add(initial_status)

                added_count += 1
                logger.info(f"Added data source: {source_data['name']}")

            db.session.commit()
            logger.info(f"Successfully added {added_count} new data sources")

            # Show all data sources
            all_sources = DataSource.query.all()
            logger.info(f"\nTotal data sources: {len(all_sources)}")
            for source in all_sources:
                logger.info(f"  - {source.name} (scraper_key: {source.scraper_key})")

        except Exception as e:
            logger.error(f"Error populating data sources: {e}")
            db.session.rollback()
            raise


if __name__ == "__main__":
    populate_data_sources()
