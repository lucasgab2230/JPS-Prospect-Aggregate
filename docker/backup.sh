#!/bin/bash
# SQLite backup script for Docker container
# Backs up SQLite databases with retention management

set -e

# Configuration
BACKUP_DIR="/app/backups"
DATA_DIR="/app/data"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output (works in Docker)
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo -e "${GREEN}=== SQLite Docker Backup ===${NC}"
echo "Backup directory: $BACKUP_DIR"
echo "Retention: $RETENTION_DAYS days"

# Function to backup a database
backup_database() {
    local db_file="$1"
    local db_name="$(basename "$db_file" .db)"
    local backup_file="$BACKUP_DIR/${db_name}_${TIMESTAMP}.db"

    if [ -f "$db_file" ]; then
        echo -n "Backing up $db_name... "

        # Copy database file (SQLite handles locking)
        cp "$db_file" "$backup_file"

        if [ $? -eq 0 ]; then
            # Compress the backup
            gzip "$backup_file"
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${RED}✗ Failed${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠ $db_name not found${NC}"
    fi
}

# Backup databases
backup_database "$DATA_DIR/jps_aggregate.db"
backup_database "$DATA_DIR/jps_users.db"

# Clean up old backups
echo "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "*.db.gz" -type f -mtime +$RETENTION_DAYS -delete

echo -e "${GREEN}Backup completed successfully!${NC}"
