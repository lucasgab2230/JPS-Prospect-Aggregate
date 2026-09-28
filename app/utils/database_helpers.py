"""Database utility functions."""

import datetime

UTC = datetime.UTC

# import shutil # Removed as it was only used by rebuild_database
from app.utils.file_utils import clean_old_files
from app.utils.logger import logger

# from flask import current_app # Removed as it was only used by rebuild_database
# from pathlib import Path # Removed as it was only used by rebuild_database

# Set up logging using the centralized utility


def cleanup_old_backups(backup_dir, max_backups=5):
    """Clean up old database backups, keeping only the most recent ones.

    Args:
        backup_dir (str): Directory containing the backups
        max_backups (int): Maximum number of backups to keep
    """
    # Use the centralized clean_old_files function
    pattern = "proposals_backup_*.db"
    deleted = clean_old_files(backup_dir, pattern, max_backups)
    logger.info(
        f"Cleaned up {deleted} old database backup(s), keeping {max_backups} most recent"
    )
    return deleted


# Ensure datetime is imported if not already at the top of the file
# import datetime # This should be at the top of the file

# The rebuild_database function has been removed as it's unused.


def update_scraper_status(source_id: int, status: str, details: str | None = None):
    """Update the scraper status in the database for a given source_id.

    Args:
        source_id (int): The ID of the data source.
        status (str): Status to set (e.g., 'working', 'completed', 'failed').
        details (Optional[str]): Additional details or error message.
    """
    from flask import has_app_context
    # Ensure datetime is available (already imported at the top)

    logger.info(
        f"Updating scraper status for source ID {source_id} to '{status}'. Details: {details}"
    )

    # Check if we're in an application context, if not create one
    if not has_app_context():
        from app import create_app

        app = create_app()
        with app.app_context():
            return _update_scraper_status_internal(source_id, status, details)
    else:
        return _update_scraper_status_internal(source_id, status, details)


def _update_scraper_status_internal(
    source_id: int, status: str, details: str | None = None
):
    """Internal implementation of update_scraper_status that assumes we're in an app context."""
    from app.database import db
    from app.database.models import DataSource, ScraperStatus

    session = db.session
    try:
        # Verify DataSource exists
        data_source = session.query(DataSource).filter_by(id=source_id).first()
        if not data_source:
            logger.warning(
                f"DataSource with ID {source_id} not found. Cannot update status."
            )
            return

        # Find the most recent status record to update, or create a new one
        status_record = (
            session.query(ScraperStatus)
            .filter_by(source_id=source_id)
            .order_by(ScraperStatus.last_checked.desc())
            .first()
        )

        current_time = datetime.datetime.now(UTC)

        if not status_record:
            status_record = ScraperStatus(
                source_id=source_id,
                status=status,
                details=details,
                last_checked=current_time,
            )
            session.add(status_record)
            logger.info(
                f"Created new status record for source ID {source_id} with status '{status}'."
            )
        else:
            status_record.status = status
            status_record.details = details
            status_record.last_checked = current_time
            logger.info(
                f"Updated existing status record for source ID {source_id} to '{status}'."
            )

        session.commit()
        logger.info(f"Successfully committed status update for source ID {source_id}.")

    except Exception as e:
        logger.error(
            f"Error updating scraper status for source ID {source_id}: {str(e)}",
            exc_info=True,
        )
        try:
            session.rollback()
        except Exception as rb_exc:
            logger.error(
                f"Failed to rollback session during status update error: {rb_exc}",
                exc_info=True,
            )


def get_data_source_id_by_name(source_name: str) -> int | None:
    """Fetches the ID of a data source by its name."""
    from app.database import db
    from app.database.models import DataSource

    session = db.session
    try:
        data_source = (
            session.query(DataSource.id).filter(DataSource.name == source_name).scalar()
        )
        if data_source:
            return data_source  # scalar() directly returns the ID
        logger.warning(f"Data source not found with name: {source_name}")
        return None
    except Exception as e:
        logger.error(
            f"Error fetching data source ID for {source_name}: {str(e)}", exc_info=True
        )
        return None
