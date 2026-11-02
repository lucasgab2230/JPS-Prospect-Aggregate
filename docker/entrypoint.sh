#!/bin/bash
# Entrypoint script for JPS Prospect Aggregate with SQLite
# Simplified for SQLite database usage
set -e

echo "=== JPS Prospect Aggregate Docker Entrypoint ==="
echo "Starting JPS Prospect Aggregate application..."

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to ensure SQLite databases exist
ensure_databases() {
    log "Checking SQLite databases..."

    # Create data directory if it doesn't exist
    mkdir -p /app/data

    # Check if databases exist
    if [ -f "/app/data/jps_aggregate.db" ]; then
        log "Business database exists at /app/data/jps_aggregate.db"
    else
        log "Business database will be created on first access"
    fi

    if [ -f "/app/data/jps_users.db" ]; then
        log "User database exists at /app/data/jps_users.db"
    else
        log "User database will be created on first access"
    fi

    # Set proper permissions for the data directory
    chmod 755 /app/data
}

# Function to run migrations
run_migrations() {
    log "Running database migrations..."

    cd /app

    # Set environment variables for Flask
    export FLASK_APP=run.py
    export FLASK_ENV=${FLASK_ENV:-production}

    # Run migrations
    log "Executing flask db upgrade..."
    if flask db upgrade 2>&1; then
        log "Database migrations completed successfully"
    else
        log "WARNING: Migration issues detected, but continuing..."
        # SQLite is more forgiving, so we can continue
    fi

    # Verify tables exist without creating app instance
    log "Verifying database tables..."
    python3 << 'PYTHON_SCRIPT'
import sys
import sqlite3
import os

try:
    # Check if database file exists
    db_path = '/app/data/jps_aggregate.db'

    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check key tables
        tables = ['prospects', 'data_sources', 'scraper_status']
        for table in tables:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM {table}')
                count = cursor.fetchone()[0]
                print(f'✓ {table} table: {count} records')
            except Exception as e:
                print(f'✗ {table} table: Not found (will be created on first use)')

        conn.close()
        print('Database verification complete')
    else:
        print('Database file does not exist yet (will be created on first use)')

except Exception as e:
    print(f'Database verification error: {e}')
    print('Tables will be created on first access')
PYTHON_SCRIPT
}

# Function to initialize user database
init_user_database() {
    log "Initializing user database..."

    cd /app

    # Set environment variables
    export FLASK_APP=run.py
    export FLASK_ENV=${FLASK_ENV:-production}

    # Run user database initialization
    if python scripts/init_user_database.py 2>&1; then
        log "User database initialized successfully"
    else
        log "User database initialization skipped (may already exist)"
    fi
}

# Function to create super admin
create_super_admin() {
    log "Ensuring super admin user exists..."

    cd /app

    # Set environment variables
    export FLASK_APP=run.py
    export FLASK_ENV=${FLASK_ENV:-production}

    # Create super admin if needed
    if python scripts/create_super_admin.py 2>&1; then
        log "Super admin check completed"
    else
        log "Super admin creation skipped (may already exist)"
    fi
}

# Main execution
log "Starting JPS Prospect Aggregate Container"
log "Environment: ${FLASK_ENV:-production}"
log "Database: SQLite"
log "Platform: $(uname -s)"

ensure_databases
run_migrations
init_user_database
create_super_admin

log "Starting application with command: $@"
exec "$@"
