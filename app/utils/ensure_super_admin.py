"""Ensure super admin user exists on application startup.

This module provides functionality to automatically create or update
the default super admin user when the application starts.
"""

from app.database import db
from app.database.user_models import User
from app.utils.logger import logger


def ensure_super_admin_exists():
    """Ensure the default super admin user exists.

    Creates the user if they don't exist, or upgrades them to super_admin
    if they exist with a different role.

    Returns:
        bool: True if successful, False otherwise
    """
    # Default super admin credentials
    email = "zcanepa@jps-online.com"
    first_name = "Zach"

    try:
        # Check if user already exists
        existing_user = db.session.query(User).filter_by(email=email.lower()).first()

        if existing_user:
            if existing_user.role == "super_admin":
                logger.debug(f"Super admin '{email}' already exists")
                return True
            # Update existing user to super_admin
            logger.info(
                f"Upgrading user '{email}' from role '{existing_user.role}' to super_admin"
            )
            existing_user.role = "super_admin"
            db.session.commit()
            logger.info(f"✅ Successfully upgraded '{email}' to super_admin")
            return True

        # Create new super admin user
        user = User(email=email.lower(), first_name=first_name, role="super_admin")

        db.session.add(user)
        db.session.commit()

        logger.info(f"✅ Created default super_admin user: {email}")

        return True

    except Exception as e:
        logger.warning(f"Failed to ensure super admin exists: {str(e)}")
        db.session.rollback()
        # Don't fail the app startup over this
        return False
