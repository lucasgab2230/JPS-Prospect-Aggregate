#!/bin/bash
# SQLite Backup Script
# Simple, reliable backups for SQLite databases

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_ROOT/data"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo -e "${GREEN}=== SQLite Backup Script ===${NC}"
echo "Backup directory: $BACKUP_DIR"
echo "Retention: $RETENTION_DAYS days"
echo ""

# Function to backup a database
backup_database() {
    local db_file="$1"
    local db_name="$(basename "$db_file" .db)"
    local backup_file="$BACKUP_DIR/${db_name}_${TIMESTAMP}.db"

    if [ -f "$db_file" ]; then
        echo -n "Backing up $db_name... "

        # Use SQLite's backup command for consistency
        sqlite3 "$db_file" ".backup '$backup_file'" 2>/dev/null

        if [ $? -eq 0 ]; then
            # Compress the backup
            gzip "$backup_file"
            local size=$(ls -lh "${backup_file}.gz" | awk '{print $5}')
            echo -e "${GREEN}✓${NC} (${size})"
        else
            echo -e "${RED}✗ Failed${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠ $db_name not found, skipping${NC}"
    fi
}

# Backup main databases
backup_database "$DATA_DIR/jps_aggregate.db"
backup_database "$DATA_DIR/jps_users.db"

# Clean up old backups
echo ""
echo "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "*.db.gz" -type f -mtime +$RETENTION_DAYS -delete

# Show backup summary
echo ""
echo -e "${GREEN}=== Backup Summary ===${NC}"
echo "Current backups:"
ls -lh "$BACKUP_DIR"/*.db.gz 2>/dev/null | tail -5 || echo "No backups found"

# Show disk usage
echo ""
echo "Backup directory size: $(du -sh "$BACKUP_DIR" | cut -f1)"
echo ""
echo -e "${GREEN}Backup completed successfully!${NC}"
