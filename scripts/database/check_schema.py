#!/usr/bin/env python
"""Quick script to check for database schema mismatches.

Usage:
    python scripts/check_schema.py
"""

import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.models import Prospect


def check_schema_sync():
    """Check if database schema matches model definitions."""
    db_path = Path(__file__).parent.parent / "data" / "jps_aggregate.db"

    if not db_path.exists():
        print("❌ Database file not found!")
        return False

    # Get model columns
    model_columns = set(column.name for column in Prospect.__table__.columns)

    # Get database columns
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(prospects)")
    db_columns = set(row[1] for row in cursor.fetchall())

    # Check for mismatches
    only_in_model = model_columns - db_columns
    only_in_db = db_columns - model_columns

    if only_in_model or only_in_db:
        print("❌ Schema mismatch detected!")

        if only_in_model:
            print(f"   Columns in model but not in database: {only_in_model}")
            print(
                "   Run: flask db migrate -m 'Add missing columns' && flask db upgrade"
            )

        if only_in_db:
            print(f"   Columns in database but not in model: {only_in_db}")
            print("   These may be old columns that need cleanup")

        conn.close()
        return False
    print("✅ Database schema matches model definitions")

    # Also check if migrations are tracked
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
    )
    if cursor.fetchone():
        print("✅ Migration tracking is active")
    else:
        print("⚠️  Migration tracking not initialized - run: flask db stamp head")

    conn.close()
    return True


if __name__ == "__main__":
    success = check_schema_sync()
    sys.exit(0 if success else 1)
