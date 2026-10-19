"""Cleanup utility for stuck scraper processes.

This module provides functions to clean up scraper statuses that may be
stuck due to server restarts, crashes, or unexpected shutdowns.
"""

from datetime import UTC

UTC = UTC
from datetime import datetime, timedelta

from app.database import db
from app.database.models import DataSource, ScraperStatus
from app.utils.logger import logger


def cleanup_stuck_scrapers(max_age_hours=2):
    """Reset scraper statuses that have been stuck for too long.

    Args:
        max_age_hours (int): Maximum hours a scraper can be 'working'
                           before being considered stuck. Default is 2 hours.

    Returns:
        int: Number of scrapers that were cleaned up
    """
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        # Find scrapers that are stuck in working status
        stuck_scrapers = (
            db.session.query(ScraperStatus)
            .filter(
                ScraperStatus.status == "working",
                ScraperStatus.last_checked < cutoff_time,
            )
            .all()
        )

        if not stuck_scrapers:
            logger.info("No stuck scrapers found")
            return 0

        count = len(stuck_scrapers)
        logger.info(f"Found {count} stuck scrapers, cleaning up...")

        # Reset their status to failed with timeout message
        for scraper_status in stuck_scrapers:
            data_source = db.session.query(DataSource).get(scraper_status.source_id)
            source_name = (
                data_source.name
                if data_source
                else f"Source ID {scraper_status.source_id}"
            )

            logger.info(
                f"Resetting stuck scraper: {source_name} (stuck since {scraper_status.last_checked})"
            )

            scraper_status.status = "failed"
            scraper_status.details = f"Automatically reset after {max_age_hours} hours timeout - scraper appeared to be stuck"
            scraper_status.last_checked = datetime.utcnow()

        db.session.commit()
        logger.info(f"Successfully cleaned up {count} stuck scrapers")
        return count

    except Exception as e:
        logger.error(f"Error cleaning up stuck scrapers: {e}")
        db.session.rollback()
        raise


def cleanup_all_working_scrapers():
    """Reset scrapers that have been marked 'working' for more than 2 hours.

    This avoids interfering with legitimately running scrapers while still
    cleaning up truly stuck ones from server restarts or crashes.

    Returns:
        int: Number of scrapers that were reset
    """
    try:
        from datetime import datetime, timedelta

        # Only clean up scrapers that have been working for more than 2 hours
        cutoff_time = datetime.now(UTC) - timedelta(hours=2)

        stuck_working_scrapers = (
            db.session.query(ScraperStatus)
            .filter(
                ScraperStatus.status == "working",
                ScraperStatus.last_checked < cutoff_time,
            )
            .all()
        )

        if not stuck_working_scrapers:
            logger.info("No stuck working scrapers found")
            return 0

        count = len(stuck_working_scrapers)
        logger.info(f"Found {count} stuck working scrapers, resetting to failed...")

        for scraper_status in stuck_working_scrapers:
            data_source = db.session.query(DataSource).get(scraper_status.source_id)
            source_name = (
                data_source.name
                if data_source
                else f"Source ID {scraper_status.source_id}"
            )

            logger.info(f"Resetting scraper: {source_name}")
            scraper_status.status = "failed"
            scraper_status.details = (
                "Reset due to server restart - processing state was lost"
            )
            scraper_status.last_checked = datetime.utcnow()

        db.session.commit()
        logger.info(f"Successfully reset {count} scraper statuses to failed")
        return count

    except Exception as e:
        logger.error(f"Error resetting scraper statuses: {e}")
        db.session.rollback()
        raise


def get_scraper_statistics():
    """Get statistics about current scraper statuses.

    Returns:
        dict: Statistics about scraper statuses
    """
    try:
        stats = {}

        # Count by status
        for status in ["working", "completed", "failed"]:
            count = (
                db.session.query(ScraperStatus)
                .filter(ScraperStatus.status == status)
                .count()
            )
            stats[status] = count

        # Count long-running scrapers (over 2 hours)
        cutoff_time = datetime.utcnow() - timedelta(hours=2)
        long_running = (
            db.session.query(ScraperStatus)
            .filter(
                ScraperStatus.status == "working",
                ScraperStatus.last_checked < cutoff_time,
            )
            .count()
        )
        stats["long_running"] = long_running

        # Count stuck scrapers (over 1 hour but less than timeout)
        stuck_cutoff = datetime.utcnow() - timedelta(hours=1)
        potentially_stuck = (
            db.session.query(ScraperStatus)
            .filter(
                ScraperStatus.status == "working",
                ScraperStatus.last_checked < stuck_cutoff,
            )
            .count()
        )
        stats["potentially_stuck"] = potentially_stuck

        # Total scrapers
        stats["total"] = db.session.query(ScraperStatus).count()

        return stats

    except Exception as e:
        logger.error(f"Error getting scraper statistics: {e}")
        return {}


def is_scraper_stuck(source_id, max_age_hours=2):
    """Check if a specific scraper is stuck.

    Args:
        source_id (int): The data source ID to check
        max_age_hours (int): Maximum hours before considering stuck

    Returns:
        bool: True if the scraper is stuck, False otherwise
    """
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        scraper_status = (
            db.session.query(ScraperStatus)
            .filter(
                ScraperStatus.source_id == source_id,
                ScraperStatus.status == "working",
                ScraperStatus.last_checked < cutoff_time,
            )
            .first()
        )

        return scraper_status is not None

    except Exception as e:
        logger.error(f"Error checking if scraper {source_id} is stuck: {e}")
        return False


def reset_scraper_status(source_id, status="failed", details=None):
    """Safely reset a specific scraper's status.

    Args:
        source_id (int): The data source ID to reset
        status (str): New status to set (default: 'failed')
        details (str): Optional details message

    Returns:
        bool: True if reset was successful, False otherwise
    """
    try:
        scraper_status = (
            db.session.query(ScraperStatus)
            .filter(ScraperStatus.source_id == source_id)
            .first()
        )

        if not scraper_status:
            logger.warning(f"No scraper status found for source ID {source_id}")
            return False

        old_status = scraper_status.status
        scraper_status.status = status
        scraper_status.details = (
            details or f"Status reset from {old_status} to {status}"
        )
        scraper_status.last_checked = datetime.utcnow()

        db.session.commit()
        logger.info(f"Reset scraper {source_id} status from {old_status} to {status}")
        return True

    except Exception as e:
        logger.error(f"Error resetting scraper {source_id} status: {e}")
        db.session.rollback()
        return False
