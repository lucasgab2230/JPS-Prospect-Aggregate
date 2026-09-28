"""Scraper Utilities

Replaces ScraperService with simple utility functions.
Provides scraper execution, status management, and error handling.
"""

import asyncio
import threading
from datetime import UTC

UTC = UTC
from datetime import datetime

from app.config import active_config
from app.core.scrapers import SCRAPERS
from app.database.models import DataSource, ScraperStatus
from app.exceptions import NotFoundError, ScraperError
from app.utils.database_helpers import update_scraper_status
from app.utils.logger import logger

# Thread locks for preventing concurrent scraping
_scraper_locks = {}
_locks_mutex = threading.Lock()


def get_or_create_scraper_lock(source_id: int) -> threading.Lock:
    """Get or create a lock for a specific source ID."""
    with _locks_mutex:
        if source_id not in _scraper_locks:
            _scraper_locks[source_id] = threading.Lock()
        return _scraper_locks[source_id]


def trigger_scraper(source_id: int) -> dict[str, any]:
    """Trigger a scraper for the given source ID.
    Returns dict with status and message.
    """
    # Get lock for this source ID to prevent concurrent execution
    scraper_lock = get_or_create_scraper_lock(source_id)

    # Try to acquire lock without blocking
    if not scraper_lock.acquire(blocking=False):
        raise ScraperError(f"Scraper for source ID {source_id} is already running")

    try:
        # Clean up any stuck scrapers before starting new ones
        if active_config.SCRAPER_CLEANUP_ENABLED:
            cleanup_count = cleanup_stuck_scrapers(
                max_age_hours=getattr(active_config, "SCRAPER_TIMEOUT_HOURS", 2)
            )
            if cleanup_count > 0:
                logger.info(
                    f"Cleaned up {cleanup_count} stuck scrapers before starting new scrape"
                )

        # Get data source
        data_source = DataSource.query.get(source_id)
        if not data_source:
            raise NotFoundError(f"Data source with ID {source_id} not found")

        # Find appropriate scraper
        scraper_key = data_source.scraper_key
        if scraper_key not in SCRAPERS:
            raise ScraperError(f"No scraper found for source: {scraper_key}")

        scraper_class = SCRAPERS[scraper_key]

        # Update status to working
        update_scraper_status(source_id, "working", "Scraper started")

        # Run scraper in background thread
        def run_scraper():
            # Create Flask application context for database operations
            from app import create_app

            app = create_app()

            try:
                with app.app_context():
                    try:
                        # Create and run scraper
                        scraper = scraper_class()

                        # Run the scraper (handle both sync and async methods)
                        if not hasattr(scraper, "scrape"):
                            raise ScraperError(
                                f"Scraper {scraper_key} does not have a scrape method"
                            )

                        import inspect

                        # Check if the scrape method is a coroutine
                        if inspect.iscoroutinefunction(scraper.scrape):
                            # It's an async method, run it in a new event loop
                            try:
                                # Always use asyncio.run to avoid event loop conflicts
                                result = asyncio.run(scraper.scrape())
                            except RuntimeError as e:
                                if "cannot be called from a running event loop" in str(
                                    e
                                ):
                                    # If we're in a running event loop, use thread executor
                                    import concurrent.futures

                                    with (
                                        concurrent.futures.ThreadPoolExecutor() as executor
                                    ):
                                        future = executor.submit(
                                            asyncio.run, scraper.scrape()
                                        )
                                        result = future.result()
                                else:
                                    raise e
                        else:
                            # It's a synchronous method
                            result = scraper.scrape()

                        # Update status to completed
                        update_scraper_status(
                            source_id, "completed", f"Scraped {result} records"
                        )
                        logger.info(
                            f"Scraper {scraper_key} completed successfully with {result} records"
                        )

                    except Exception as e:
                        error_msg = f"Scraper failed: {str(e)}"
                        logger.error(
                            f"Scraper {scraper_key} failed: {e}", exc_info=True
                        )

                        # Ensure status is updated to failed even if there are app context issues
                        try:
                            update_scraper_status(source_id, "failed", error_msg)
                        except Exception as status_error:
                            logger.error(
                                f"Failed to update scraper status to failed: {status_error}"
                            )

            except Exception as outer_e:
                # This catches any issues with app context creation itself
                logger.error(
                    f"Critical error in scraper thread for {scraper_key}: {outer_e}",
                    exc_info=True,
                )
                # Try one more time to update status without app context dependency
                try:
                    from app import create_app

                    app = create_app()
                    with app.app_context():
                        update_scraper_status(
                            source_id,
                            "failed",
                            f"Critical scraper error: {str(outer_e)}",
                        )
                except Exception:
                    logger.error(
                        f"Could not update status after critical error for source {source_id}"
                    )
            finally:
                # Always release the lock, no matter what happened
                try:
                    scraper_lock.release()
                except Exception as lock_error:
                    logger.error(f"Error releasing scraper lock: {lock_error}")

        # Start scraper thread
        thread = threading.Thread(target=run_scraper, daemon=True)
        thread.start()

        return {
            "status": "started",
            "message": f"Scraper for {data_source.name} started successfully",
            "source_id": source_id,
        }

    except Exception as e:
        scraper_lock.release()
        raise e


def get_scraper_status(source_id: int) -> dict[str, any]:
    """Get current scraper status for a source."""
    try:
        status = ScraperStatus.query.filter_by(source_id=source_id).first()
        if not status:
            return {
                "source_id": source_id,
                "status": "pending",
                "message": "Ready to run",
                "last_run": None,
            }

        return {
            "source_id": source_id,
            "status": status.status,
            "message": status.details,  # Use details field, not message
            "last_run": status.last_checked.isoformat()
            if status.last_checked
            else None,  # Use last_checked, not last_run
            "updated_at": status.last_checked.isoformat()
            if status.last_checked
            else None,  # Use last_checked for consistency
        }

    except Exception as e:
        logger.error(f"Error getting scraper status for source {source_id}: {e}")
        return {
            "source_id": source_id,
            "status": "error",
            "message": f"Error retrieving status: {str(e)}",
            "last_run": None,
        }


def get_all_scraper_statuses() -> list[dict[str, any]]:
    """Get status for all scrapers."""
    try:
        data_sources = DataSource.query.all()
        statuses = []

        for source in data_sources:
            status_info = get_scraper_status(source.id)
            status_info["source_name"] = source.name
            status_info["scraper_key"] = source.scraper_key
            statuses.append(status_info)

        return statuses

    except Exception as e:
        logger.error(f"Error getting all scraper statuses: {e}")
        return []


def stop_scraper(source_id: int) -> dict[str, any]:
    """Attempt to stop a running scraper.
    Note: This is limited since we can't forcefully stop threads.
    """
    try:
        # Update status to indicate stop was requested
        update_scraper_status(source_id, "stop_requested", "Stop requested by user")

        # Note: We can't actually force-stop a running thread in Python
        # The scraper would need to check for stop signals internally

        return {
            "status": "stop_requested",
            "message": "Stop signal sent to scraper (may take time to complete current operation)",
            "source_id": source_id,
        }

    except Exception as e:
        logger.error(f"Error stopping scraper for source {source_id}: {e}")
        return {
            "status": "error",
            "message": f"Error stopping scraper: {str(e)}",
            "source_id": source_id,
        }


def cleanup_stuck_scrapers(max_age_hours: int = 2) -> int:
    """Clean up scrapers that have been running for too long.
    Returns count of cleaned up scrapers.
    """
    try:
        from app.utils.scraper_cleanup import cleanup_stuck_scrapers as cleanup_func

        return cleanup_func(max_age_hours)
    except ImportError:
        # Fallback cleanup implementation
        from datetime import timedelta

        cutoff_time = datetime.now(UTC) - timedelta(hours=max_age_hours)

        stuck_scrapers = ScraperStatus.query.filter(
            ScraperStatus.status == "working", ScraperStatus.last_checked < cutoff_time
        ).all()

        cleanup_count = 0
        for scraper in stuck_scrapers:
            update_scraper_status(
                scraper.source_id,
                "failed",
                f"Scraper was stuck for {max_age_hours}+ hours and was cleaned up",
            )
            cleanup_count += 1

        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} stuck scrapers")

        return cleanup_count


def run_all_scrapers() -> dict[str, any]:
    """Trigger all available scrapers.
    Returns summary of results.
    """
    data_sources = DataSource.query.all()
    results = {"total": len(data_sources), "started": 0, "errors": 0, "details": []}

    for source in data_sources:
        try:
            trigger_scraper(source.id)
            results["started"] += 1
            results["details"].append(
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "status": "started",
                }
            )
        except Exception as e:
            results["errors"] += 1
            results["details"].append(
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "status": "error",
                    "error": str(e),
                }
            )

    return results


def get_available_scrapers() -> list[dict[str, str]]:
    """Get list of all available scrapers."""
    return [
        {
            "key": key,
            "class_name": scraper_class.__name__,
            "description": getattr(
                scraper_class, "__doc__", "No description available"
            ),
        }
        for key, scraper_class in SCRAPERS.items()
    ]
