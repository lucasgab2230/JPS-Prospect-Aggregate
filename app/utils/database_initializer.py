"""Database initialization helper with thread-safe operations.

This module provides centralized database setup logic with proper
locking to prevent race conditions during initialization.
"""

import threading
from contextlib import contextmanager
from datetime import datetime

from app.utils.logger import logger

# Global lock for database initialization
_init_lock = threading.Lock()
_initialized = False


class DatabaseInitializer:
    """Thread-safe database initializer."""

    def __init__(self, app=None):
        self.app = app
        self._business_initialized = False
        self._user_initialized = False

    @contextmanager
    def initialization_context(self):
        """Context manager for safe initialization."""
        global _initialized

        with _init_lock:
            if _initialized:
                yield True
                return

            try:
                yield False
            finally:
                _initialized = True

    def initialize(self, app=None):
        """Initialize databases with proper locking.

        Args:
            app: Flask application instance

        Returns:
            bool: True if successful, False otherwise
        """
        if app:
            self.app = app

        if not self.app:
            logger.error("No Flask app provided for initialization")
            return False

        with self.initialization_context() as already_done:
            if already_done:
                logger.debug("Database already initialized in this session")
                return True

            return self._perform_initialization()

    def _perform_initialization(self):
        """Perform the actual initialization."""
        try:
            from app.database.auto_init import ensure_database_ready

            logger.info("=" * 60)
            logger.info("AUTOMATIC DATABASE INITIALIZATION")
            logger.info("=" * 60)

            start_time = datetime.now()

            # Run the initialization
            success = ensure_database_ready(self.app)

            elapsed = (datetime.now() - start_time).total_seconds()

            if success:
                logger.info("=" * 60)
                logger.info(f"DATABASE READY (initialized in {elapsed:.2f}s)")
                logger.info("=" * 60)
            else:
                logger.error("=" * 60)
                logger.error("DATABASE INITIALIZATION FAILED")
                logger.error("=" * 60)

            return success

        except Exception as e:
            logger.error(f"Exception during database initialization: {e}")
            return False

    def verify_database_state(self):
        """Verify the current state of databases.

        Returns:
            dict: Status of each database component
        """
        from app.database.auto_init import check_tables_exist, check_user_tables_exist

        with self.app.app_context():
            business_ok, missing_business = check_tables_exist()
            user_ok, missing_user = check_user_tables_exist()

            return {
                "business_database": {
                    "ready": business_ok,
                    "missing_tables": missing_business,
                },
                "user_database": {"ready": user_ok, "missing_tables": missing_user},
                "overall_ready": business_ok and user_ok,
            }

    def reset_initialization_state(self):
        """Reset the initialization state (useful for testing)."""
        global _initialized
        with _init_lock:
            _initialized = False
            self._business_initialized = False
            self._user_initialized = False


# Singleton instance
_initializer = DatabaseInitializer()


def get_database_initializer():
    """Get the singleton database initializer.

    Returns:
        DatabaseInitializer: The singleton instance
    """
    return _initializer


def initialize_database(app):
    """Convenience function to initialize database.

    Args:
        app: Flask application instance

    Returns:
        bool: True if successful, False otherwise
    """
    return _initializer.initialize(app)


def verify_database():
    """Convenience function to verify database state.

    Returns:
        dict: Database status information
    """
    return _initializer.verify_database_state()
