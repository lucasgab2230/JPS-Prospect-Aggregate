"""Database initialization using Flask application context.
This module provides unified database initialization for both business and user databases.
"""

from app.utils.logger import logger


def initialize_business_database(app):
    """Initialize the business database with all tables."""
    from app.database import db

    with app.app_context():
        logger.info("Initializing business database...")

        try:
            # Create all tables for the main bind
            db.create_all()
            logger.info("Business database initialized successfully!")
            return True

        except Exception as e:
            logger.error(f"Error initializing business database: {e}")
            return False


def initialize_user_database(app):
    """Initialize the user database with all tables."""
    from app.database import db

    with app.app_context():
        logger.info("Initializing user database...")

        try:
            # Create all tables in the users bind
            db.create_all(bind_key="users")
            logger.info("User database initialized successfully!")
            return True

        except Exception as e:
            logger.error(f"Error initializing user database: {e}")
            return False


def initialize_all_databases(app):
    """Initialize both business and user databases."""
    business_success = initialize_business_database(app)
    user_success = initialize_user_database(app)

    if business_success and user_success:
        logger.info("All databases initialized successfully!")
        return True
    logger.error("Failed to initialize one or more databases")
    return False


if __name__ == "__main__":
    logger.info("Running database initialization script...")
    from app import create_app

    app = create_app()
    success = initialize_all_databases(app)
    if success:
        logger.info("Database initialization completed successfully.")
    else:
        logger.error("Database initialization failed.")
        exit(1)
