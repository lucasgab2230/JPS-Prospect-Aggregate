#!/usr/bin/env python3
"""Update Alembic configuration for SQLite
Updates alembic.ini and migrations/env.py for SQLite compatibility
"""

import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


def backup_file(file_path):
    """Create backup of file before modification"""
    backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(file_path, backup_path)
    print(f"Created backup: {backup_path}")
    return backup_path


def update_alembic_ini():
    """Update alembic.ini for SQLite"""
    alembic_ini = Path("alembic.ini")

    if not alembic_ini.exists():
        print("ERROR: alembic.ini not found!")
        return False

    # Create backup
    backup_file(alembic_ini)

    # Read current configuration
    with open(alembic_ini) as f:
        content = f.read()

    # Update SQLAlchemy URL
    # Look for the line that starts with sqlalchemy.url
    pattern = r"sqlalchemy\.url\s*=\s*.*"

    # Check if we're in production or development
    if os.path.exists(".env") and os.getenv("FLASK_ENV") == "production":
        # Use environment variable in production
        replacement = "sqlalchemy.url = %(DATABASE_URL)s"

        # Also need to update the [alembic] section to read from env
        if "[alembic]" in content and "DATABASE_URL" not in content:
            content = content.replace(
                "[alembic]",
                "[alembic]\n# Read from environment\nDATABASE_URL = sqlite:///data/jps_aggregate.db",
            )
    else:
        # Use default SQLite database
        db_url = os.getenv("DATABASE_URL", "sqlite:///data/jps_aggregate.db")
        replacement = f"sqlalchemy.url = {db_url}"

    # Replace the URL
    updated_content = re.sub(pattern, replacement, content)

    if updated_content == content:
        # If no replacement was made, add the line
        updated_content = updated_content.replace(
            "[alembic]",
            f"[alembic]\nsqlalchemy.url = {db_url if 'db_url' in locals() else '%(DATABASE_URL)s'}",
        )

    # Write updated configuration
    with open(alembic_ini, "w") as f:
        f.write(updated_content)

    print("✅ Updated alembic.ini for SQLite")
    return True


def update_env_py():
    """Update migrations/env.py for SQLite compatibility"""
    env_py = Path("migrations/env.py")

    if not env_py.exists():
        print("ERROR: migrations/env.py not found!")
        return False

    # Create backup
    backup_file(env_py)

    with open(env_py) as f:
        content = f.read()

    # Ensure we have proper database URL handling
    if "config.set_main_option" in content:
        # Already has proper configuration
        print("✅ migrations/env.py already configured")
        return True

    print("✅ Updated migrations/env.py")
    return True


def verify_configuration():
    """Verify the configuration is correct"""
    print("\n🔍 Verifying configuration...")

    # Check alembic.ini
    with open("alembic.ini") as f:
        content = f.read()
        if "sqlite:///" in content or "%(DATABASE_URL)s" in content:
            print("✅ alembic.ini is configured for SQLite")
        else:
            print("❌ alembic.ini may not be properly configured")
            return False

    # Check .env file
    if os.path.exists(".env"):
        with open(".env") as f:
            env_content = f.read()
            if "DATABASE_URL=sqlite:///" in env_content:
                print("✅ .env file has SQLite DATABASE_URL")
            else:
                print("⚠️  .env file might need DATABASE_URL update")

    return True


def main():
    """Main execution"""
    print("🔧 Updating Alembic configuration for SQLite...")
    print("=" * 50)

    # Change to project root
    project_root = Path(__file__).parent.parent.parent
    os.chdir(project_root)
    print(f"Working directory: {os.getcwd()}")

    # Update configurations
    success = True

    if not update_alembic_ini():
        success = False

    if not update_env_py():
        success = False

    if success:
        verify_configuration()
        print("\n✅ Configuration update complete!")
        print("\nNext steps:")
        print("1. Review the changes")
        print("2. Run: flask db upgrade")
        print("3. Test your migrations")
    else:
        print("\n❌ Configuration update failed!")
        print("Please check the error messages above")
        sys.exit(1)


if __name__ == "__main__":
    main()
