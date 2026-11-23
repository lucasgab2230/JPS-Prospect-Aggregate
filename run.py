#!/usr/bin/env python
"""JPS Prospect Aggregate Application Launcher
===========================================

This script starts the Flask web application using the Waitress WSGI server.
Database initialization is handled automatically on startup.
"""

import os
import sys
from pathlib import Path

from waitress import serve

from app import create_app
from app.utils.logger import logger

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Environment variables are loaded by app.config during app creation

# Get configuration from environment variables
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 5001))
DEBUG = (
    os.getenv("FLASK_DEBUG", "False").lower() == "true"
)  # Use FLASK_DEBUG for waitress compatibility

# Pre-flight checks
logger.info("=" * 60)
logger.info("JPS PROSPECT AGGREGATE - STARTING")
logger.info("=" * 60)

# Ensure data directory exists
data_dir = Path("data")
if not data_dir.exists():
    data_dir.mkdir(parents=True)
    logger.info("Created data directory")

# Create the Flask app instance (this will auto-initialize database)
logger.info("Initializing application...")
app = create_app()

# Verify database state
from app.utils.database_initializer import get_database_initializer

db_status = get_database_initializer().verify_database_state()

if not db_status.get("overall_ready", False):
    logger.error("=" * 60)
    logger.error("DATABASE NOT READY - APPLICATION MAY NOT FUNCTION PROPERLY")
    logger.error(f"Business DB ready: {db_status['business_database']['ready']}")
    logger.error(f"User DB ready: {db_status['user_database']['ready']}")
    logger.error("=" * 60)
else:
    logger.info("Database verification: PASSED")


def main():
    """Main entry point to start the server."""
    logger.info("=" * 60)
    if DEBUG:
        logger.info(f"Starting Flask DEVELOPMENT server on http://{HOST}:{PORT}")
    else:
        logger.info(f"Starting PRODUCTION server on http://{HOST}:{PORT}")
    logger.info("=" * 60)

    if DEBUG:
        app.run(host=HOST, port=PORT, debug=True)
    else:
        # Use single thread to avoid session race conditions in production
        # This is fine for a small-scale application
        # ProxyFix is applied to app.wsgi_app internally, so serving app works correctly
        serve(app, host=HOST, port=PORT, threads=1)


if __name__ == "__main__":
    main()
