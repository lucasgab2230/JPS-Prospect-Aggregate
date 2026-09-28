"""Automatic database initialization module.

This module handles automatic database setup on application startup,
ensuring tables exist without requiring manual intervention.
"""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import inspect

from app.database import db
from app.utils.logger import logger


def check_tables_exist(required_tables=None):
    """Check if required database tables exist.

    Args:
        required_tables: List of table names to check. If None, checks core tables.

    Returns:
        Tuple of (bool, list) - (all_exist, missing_tables)
    """
    if required_tables is None:
        # Core tables that must exist for the app to function
        required_tables = [
            "prospects",
            "data_sources",
            "scraper_status",
            "go_no_go_decisions",
            "file_processing_log",  # Note: singular, not plural
        ]

    try:
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        missing = [table for table in required_tables if table not in existing_tables]

        if missing:
            logger.info(f"Missing tables: {', '.join(missing)}")
            return False, missing

        return True, []

    except Exception as e:
        logger.error(f"Error checking tables: {e}")
        return False, required_tables


def check_user_tables_exist():
    """Check if user database tables exist.

    Returns:
        Tuple of (bool, list) - (all_exist, missing_tables)
    """
    required_tables = ["users"]

    try:
        # Check user database using the 'users' bind
        inspector = inspect(db.get_engine(bind_key="users"))
        existing_tables = inspector.get_table_names()

        missing = [table for table in required_tables if table not in existing_tables]

        if missing:
            logger.info(f"Missing user tables: {', '.join(missing)}")
            return False, missing

        return True, []

    except Exception as e:
        logger.error(f"Error checking user tables: {e}")
        return False, required_tables


def run_migrations():
    """Run database migrations using Alembic.

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Running database migrations...")

        # Set the FLASK_APP environment variable
        env = os.environ.copy()
        env["FLASK_APP"] = "run.py"

        # Get the database URL from config
        from flask import current_app

        env["DATABASE_URL"] = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")

        # Run migrations
        result = subprocess.run(
            [sys.executable, "-m", "flask", "db", "upgrade", "head"],
            capture_output=True,
            text=True,
            env=env,
            cwd=Path(__file__).parent.parent.parent,  # Project root
        )

        if result.returncode == 0:
            logger.info("Migrations completed successfully")
            return True
        logger.error(f"Migration failed: {result.stderr}")
        return False

    except Exception as e:
        logger.error(f"Error running migrations: {e}")
        return False


def create_tables_directly():
    """Create all tables directly using SQLAlchemy.

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Creating tables directly...")

        # Import all models to ensure they're registered
        from app.database import models  # noqa
        from app.database import user_models  # noqa

        # Create all tables for main database
        db.create_all()
        logger.info("Business database tables created")

        # Create all tables for user database
        db.create_all(bind_key="users")
        logger.info("User database tables created")

        return True

    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        return False


def initialize_default_data():
    """Initialize default data (super admin, data sources, etc.).

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from app.utils.ensure_data_sources import ensure_all_data_sources_exist
        from app.utils.ensure_super_admin import ensure_super_admin_exists

        # Ensure super admin exists
        ensure_super_admin_exists()

        # Ensure data sources exist
        changes = ensure_all_data_sources_exist()
        if changes > 0:
            logger.info(f"Created/updated {changes} data sources")

        return True

    except Exception as e:
        logger.error(f"Error initializing default data: {e}")
        return False


def auto_initialize_database(app):
    """Automatically initialize database if tables don't exist.

    This function:
    1. Checks if tables exist
    2. If not, creates tables directly (migrations can be run manually later)
    3. Initializes default data

    Args:
        app: Flask application instance

    Returns:
        bool: True if database is ready, False if initialization failed
    """
    with app.app_context():
        # Check business database tables
        business_exists, missing_business = check_tables_exist()

        # Check user database tables
        user_exists, missing_user = check_user_tables_exist()

        if business_exists and user_exists:
            logger.info("All database tables exist")
            # Still ensure default data exists
            initialize_default_data()
            return True

        logger.info("Database initialization required")
        logger.info(f"Missing business tables: {missing_business}")
        logger.info(f"Missing user tables: {missing_user}")

        # Skip migrations for now - they can be run manually if needed
        # Migrations are causing subprocess hangs, so we'll create tables directly
        logger.info("Creating database tables directly...")

        if create_tables_directly():
            # Final verification
            business_exists, _ = check_tables_exist()
            user_exists, _ = check_user_tables_exist()

            if business_exists and user_exists:
                logger.info("Database initialized successfully")
                initialize_default_data()
                return True

        logger.error("Failed to initialize database")
        return False


def ensure_database_ready(app):
    """Ensure database is ready for use, initializing if necessary.

    This is the main entry point for automatic database initialization.

    Args:
        app: Flask application instance

    Returns:
        bool: True if database is ready, False otherwise
    """
    try:
        # Create data directory if it doesn't exist
        data_dir = Path("data")
        if not data_dir.exists():
            data_dir.mkdir(parents=True)
            logger.info("Created data directory")

        # Check and initialize database
        return auto_initialize_database(app)

    except Exception as e:
        logger.error(f"Critical error in database initialization: {e}")
        return False
