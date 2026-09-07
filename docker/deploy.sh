#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting deployment process...${NC}"

# Function to show maintenance page
enable_maintenance() {
    echo -e "${YELLOW}Enabling maintenance mode...${NC}"
    docker run -d --name maintenance-page \
        -p 5001:80 \
        --network jps-network \
        -v $(pwd)/docker/maintenance.html:/usr/share/nginx/html/index.html:ro \
        nginx:alpine || true
}

# Function to disable maintenance page
disable_maintenance() {
    echo -e "${YELLOW}Disabling maintenance mode...${NC}"
    docker rm -f maintenance-page 2>/dev/null || true
}

# Function to backup databases
backup_databases() {
    echo -e "${YELLOW}Backing up databases before deployment...${NC}"
    docker exec jps-backup /backup.sh
}

# Function to run migrations
run_migrations() {
    echo -e "${YELLOW}Running database migrations...${NC}"
    docker exec jps-web alembic upgrade head
}

# Main deployment process
main() {
    # Enable maintenance mode
    enable_maintenance

    # Backup databases
    backup_databases

    # Pull latest images
    echo -e "${YELLOW}Pulling latest images...${NC}"
    docker-compose pull

    # Build new image
    echo -e "${YELLOW}Building application image...${NC}"
    docker-compose build web

    # Stop current web container
    echo -e "${YELLOW}Stopping current web container...${NC}"
    docker-compose stop web

    # Start new web container
    echo -e "${YELLOW}Starting new web container...${NC}"
    docker-compose up -d web

    # Wait for web to be healthy
    echo -e "${YELLOW}Waiting for application to be ready...${NC}"
    sleep 10

    # Run migrations
    run_migrations

    # Disable maintenance mode
    disable_maintenance

    # Health check
    if curl -f http://localhost:5001/health > /dev/null 2>&1; then
        echo -e "${GREEN}Deployment completed successfully!${NC}"
    else
        echo -e "${RED}Health check failed! Check logs with: docker logs jps-web${NC}"
        exit 1
    fi
}

# Run main deployment
main
