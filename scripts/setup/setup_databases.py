#!/usr/bin/env python3
"""Comprehensive database setup script that:
1. Initializes the user authentication database
2. Runs Flask migrations for the business database
3. Populates initial data sources
4. Verifies database creation

Run this for complete database setup.
"""

import os
import subprocess
import sys
from pathlib import Path

# Add the app directory to the Python path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))

from app.utils.logger import logger


def run_command(command, description):
    """Run a command and handle output."""
    logger.info(f"{description}...")
    try:
        # Use the current Python interpreter explicitly
        if command.startswith("python "):
            command = command.replace("python ", f"{sys.executable} ", 1)
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            logger.success(f"{description} - Success!")
            if result.stdout:
                logger.debug(result.stdout)
        else:
            logger.error(f"{description} - Failed!")
            if result.stderr:
                logger.error(f"Error: {result.stderr}")
            if result.stdout:
                logger.debug(f"Output: {result.stdout}")
            return False
    except Exception as e:
        logger.exception(f"{description} - Exception: {str(e)}")
        return False
    return True


def main():
    logger.info("Setting up JPS Prospect Aggregate Databases")
    logger.info("=" * 50)

    # Check if we're in the right directory
    if not os.path.exists("requirements.txt"):
        logger.error("Please run this script from the project root directory")
        return False

    # Step 1: Initialize user database
    logger.info("\nStep 1: Initializing User Database")
    if not run_command(
        "python scripts/init_user_database.py", "Creating user authentication database"
    ):
        logger.error(
            "Failed to initialize user database. Please check the error above."
        )
        return False

    # Step 2: Run Flask migrations for business database
    logger.info("\nStep 2: Running Database Migrations")
    # Use python -m flask to ensure we use the right Flask
    if not run_command(
        f"{sys.executable} -m flask db upgrade head", "Applying database migrations"
    ):
        logger.error("Failed to run migrations. Please check the error above.")
        return False

    # Step 3: Populate data sources
    logger.info("\nStep 3: Populating Data Sources")
    if not run_command(
        "python scripts/populate_data_sources.py", "Adding initial data sources"
    ):
        logger.warning(
            "Failed to populate data sources. You can run this manually later."
        )
        # Don't fail the setup for this

    # Step 4: Check if databases were created
    logger.info("\nStep 4: Verifying Database Creation")
    data_dir = Path("data")
    user_db = data_dir / "jps_users.db"
    business_db = data_dir / "jps_aggregate.db"

    if user_db.exists():
        logger.success(f"User database created: {user_db}")
    else:
        logger.error(f"User database not found at: {user_db}")
        return False

    if business_db.exists():
        logger.success(f"Business database created: {business_db}")
    else:
        logger.error(f"Business database not found at: {business_db}")
        return False

    logger.info("\n" + "=" * 50)
    logger.success("Database Setup Complete!")
    logger.info("\nNext steps:")
    logger.info("1. Start the Flask server: python run.py")
    logger.info("2. Start the frontend: cd frontend-react && npm run dev")
    logger.info("3. Visit http://localhost:5001 and create an account!")
    logger.info("\nBackup your databases regularly with: ./scripts/backup.sh")

    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("\nSetup interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"\nUnexpected error: {str(e)}")
        sys.exit(1)
