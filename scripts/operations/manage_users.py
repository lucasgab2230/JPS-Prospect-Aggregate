#!/usr/bin/env python
"""Unified user management script for JPS Prospect Aggregate.

This script combines functionality for creating and managing user accounts.

Usage:
    python scripts/manage_users.py create-admin <email>
    python scripts/manage_users.py promote <email>
    python scripts/manage_users.py list-users
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.database import db
from app.database.user_models import User
from app.utils.logger import logger


def create_super_admin(email: str, first_name: str = None) -> bool:
    """Create a new super admin user (email-only authentication)."""
    try:
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            logger.warning(f"User with email {email} already exists")
            return False

        # Get first name if not provided
        if not first_name:
            first_name = input("Enter first name: ").strip()

            if not first_name:
                logger.error("First name is required")
                return False

        # Create new user
        user = User(email=email, first_name=first_name, role="super-admin")

        db.session.add(user)
        db.session.commit()

        logger.info(f"Super admin user created successfully: {email}")
        return True

    except Exception as e:
        logger.error(f"Error creating super admin: {e}")
        db.session.rollback()
        return False


def promote_to_super_admin(email: str) -> bool:
    """Promote an existing user to super admin."""
    try:
        user = User.query.filter_by(email=email).first()

        if not user:
            logger.error(f"User with email {email} not found")
            return False

        if user.role == "super-admin":
            logger.info(f"User {email} is already a super admin")
            return True

        user.role = "super-admin"
        db.session.commit()

        logger.info(f"User {email} promoted to super admin")
        return True

    except Exception as e:
        logger.error(f"Error promoting user: {e}")
        db.session.rollback()
        return False


def list_users() -> None:
    """List all users in the system."""
    try:
        users = User.query.all()

        if not users:
            print("No users found")
            return

        print(f"\n{'Email':<40} {'Role':<15} {'Created':<20}")
        print("-" * 75)

        for user in users:
            created = (
                user.created_at.strftime("%Y-%m-%d %H:%M")
                if user.created_at
                else "Unknown"
            )
            print(f"{user.email:<40} {user.role or 'user':<15} {created:<20}")

        print(f"\nTotal users: {len(users)}")

    except Exception as e:
        logger.error(f"Error listing users: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Manage JPS Prospect Aggregate users")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create admin command
    create_parser = subparsers.add_parser(
        "create-admin", help="Create a new super admin user"
    )
    create_parser.add_argument("email", help="Email address for the new admin")
    create_parser.add_argument(
        "--first-name", help="First name (will prompt if not provided)"
    )

    # Promote command
    promote_parser = subparsers.add_parser(
        "promote", help="Promote existing user to super admin"
    )
    promote_parser.add_argument("email", help="Email address of user to promote")

    # List users command
    subparsers.add_parser("list-users", help="List all users")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Create app context
    app = create_app()

    with app.app_context():
        if args.command == "create-admin":
            success = create_super_admin(args.email, args.first_name)
            return 0 if success else 1

        if args.command == "promote":
            success = promote_to_super_admin(args.email)
            return 0 if success else 1

        if args.command == "list-users":
            list_users()
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
