#!/bin/bash
# SQLite Restore Script
# Restore SQLite databases from backups

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_ROOT/data"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== SQLite Restore Script ===${NC}"
echo ""

# Function to list available backups
list_backups() {
    local db_name="$1"
    echo "Available backups for $db_name:"
    ls -1t "$BACKUP_DIR"/${db_name}_*.db.gz 2>/dev/null | head -10 || echo "  No backups found"
}

# Function to restore a database
restore_database() {
    local db_name="$1"
    local backup_file="$2"
    local target_file="$DATA_DIR/${db_name}.db"

    if [ ! -f "$backup_file" ]; then
        echo -e "${RED}Error: Backup file not found: $backup_file${NC}"
        return 1
    fi

    echo -e "${YELLOW}Warning: This will overwrite ${target_file}${NC}"
    read -p "Are you sure you want to continue? (y/N) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Create backup of current database
        if [ -f "$target_file" ]; then
            echo "Creating backup of current database..."
            cp "$target_file" "${target_file}.before_restore_$(date +%Y%m%d_%H%M%S)"
        fi

        # Decompress and restore
        echo "Restoring from backup..."
        gunzip -c "$backup_file" > "$target_file"

        # Verify restored database
        if sqlite3 "$target_file" "PRAGMA integrity_check;" | grep -q "ok"; then
            echo -e "${GREEN}✓ Database restored successfully${NC}"
            echo "Database info:"
            echo "  Size: $(ls -lh "$target_file" | awk '{print $5}')"
            echo "  Tables: $(sqlite3 "$target_file" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>/dev/null || echo "Error reading")"
        else
            echo -e "${RED}✗ Database integrity check failed${NC}"
            return 1
        fi
    else
        echo "Restore cancelled"
        return 0
    fi
}

# Main logic
if [ $# -eq 0 ]; then
    # Interactive mode
    echo "Which database would you like to restore?"
    echo "1) jps_aggregate"
    echo "2) jps_users"
    echo "3) Both"
    read -p "Enter choice (1-3): " choice

    case $choice in
        1)
            list_backups "jps_aggregate"
            echo ""
            read -p "Enter backup filename (or 'latest' for most recent): " backup_choice
            if [ "$backup_choice" = "latest" ]; then
                backup_file=$(ls -1t "$BACKUP_DIR"/jps_aggregate_*.db.gz 2>/dev/null | head -1)
            else
                backup_file="$BACKUP_DIR/$backup_choice"
            fi
            restore_database "jps_aggregate" "$backup_file"
            ;;
        2)
            list_backups "jps_users"
            echo ""
            read -p "Enter backup filename (or 'latest' for most recent): " backup_choice
            if [ "$backup_choice" = "latest" ]; then
                backup_file=$(ls -1t "$BACKUP_DIR"/jps_users_*.db.gz 2>/dev/null | head -1)
            else
                backup_file="$BACKUP_DIR/$backup_choice"
            fi
            restore_database "jps_users" "$backup_file"
            ;;
        3)
            # Restore both databases from same timestamp
            echo "Available backup sets:"
            ls -1t "$BACKUP_DIR"/*.db.gz | sed 's/.*_\([0-9]\{8\}_[0-9]\{6\}\).*/\1/' | sort -u | head -5
            echo ""
            read -p "Enter timestamp (YYYYMMDD_HHMMSS) or 'latest': " timestamp

            if [ "$timestamp" = "latest" ]; then
                timestamp=$(ls -1t "$BACKUP_DIR"/*.db.gz | sed 's/.*_\([0-9]\{8\}_[0-9]\{6\}\).*/\1/' | sort -u | head -1)
            fi

            restore_database "jps_aggregate" "$BACKUP_DIR/jps_aggregate_${timestamp}.db.gz"
            restore_database "jps_users" "$BACKUP_DIR/jps_users_${timestamp}.db.gz"
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            exit 1
            ;;
    esac
else
    # Command line mode
    db_name="$1"
    backup_file="$2"

    if [ -z "$backup_file" ]; then
        # Use latest backup
        backup_file=$(ls -1t "$BACKUP_DIR"/${db_name}_*.db.gz 2>/dev/null | head -1)
    elif [ "$backup_file" = "latest" ]; then
        backup_file=$(ls -1t "$BACKUP_DIR"/${db_name}_*.db.gz 2>/dev/null | head -1)
    elif [[ ! "$backup_file" =~ ^/ ]]; then
        # Relative path, prepend backup directory
        backup_file="$BACKUP_DIR/$backup_file"
    fi

    restore_database "$db_name" "$backup_file"
fi

echo ""
echo -e "${BLUE}Restore process completed${NC}"
