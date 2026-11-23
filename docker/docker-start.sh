#!/bin/bash
# Docker startup script for Mac/Linux
# This script ensures a smooth Docker deployment on Unix-based systems

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
print_status "Checking prerequisites..."

if ! command_exists docker; then
    print_error "Docker is not installed. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command_exists docker-compose; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    echo "Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info >/dev/null 2>&1; then
    print_error "Docker daemon is not running. Please start Docker first."
    exit 1
fi

print_status "Prerequisites check passed!"

# Check if .env file exists
if [ ! -f .env ]; then
    print_warning ".env file not found. Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        print_status ".env file created. Please edit it with your configuration."
        print_warning "Required configurations:"
        echo "  - Set ENVIRONMENT=production"
        echo "  - Generate and set SECRET_KEY"
        echo "  - Generate and set SECRET_KEY"
        echo ""
        echo "Generate SECRET_KEY with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
        echo ""
        read -p "Press Enter after updating .env file to continue..."
    else
        print_error ".env.example file not found. Cannot create .env file."
        exit 1
    fi
fi

# Validate .env file
print_status "Validating .env configuration..."
if grep -q "CHANGE_THIS" .env; then
    print_error "Please update the placeholder values in .env file"
    print_warning "Look for CHANGE_THIS and replace with actual values"
    exit 1
fi

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p data logs backups
mkdir -p logs/error_screenshots logs/error_html

# Set correct permissions (important for volumes)
print_status "Setting directory permissions..."
chmod -R 755 data logs backups

# Check which profile to use
COMPOSE_PROFILES=""
if [ ! -z "${CLOUDFLARE_TUNNEL_TOKEN}" ]; then
    COMPOSE_PROFILES="cloudflare,"
fi

# Ask about optional services
read -p "Do you want to enable automatic container updates with Watchtower? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    COMPOSE_PROFILES="${COMPOSE_PROFILES}full"
fi

# Pull latest images
print_status "Pulling latest Docker images..."
docker-compose pull

# Build the web service
print_status "Building web application image..."
docker-compose build --no-cache web

# Start services
print_status "Starting Docker containers..."
if [ ! -z "$COMPOSE_PROFILES" ]; then
    COMPOSE_PROFILES=${COMPOSE_PROFILES%,}  # Remove trailing comma
    export COMPOSE_PROFILES
    docker-compose --profile $COMPOSE_PROFILES up -d
else
    docker-compose up -d
fi

# Wait for services to be healthy
print_status "Waiting for services to be healthy..."
sleep 10

# Check service status
print_status "Checking service status..."
docker-compose ps

# Check if web service is responding
print_status "Checking web application..."
max_attempts=30
attempt=1
while ! curl -f http://localhost:5001/health >/dev/null 2>&1; do
    if [ $attempt -eq $max_attempts ]; then
        print_error "Web application failed to start after $max_attempts attempts"
        print_status "Checking logs..."
        docker-compose logs --tail=50 web
        exit 1
    fi
    echo -n "."
    sleep 2
    attempt=$((attempt + 1))
done
echo

print_status "Web application is running!"

# Check if Ollama is ready
print_status "Checking Ollama LLM service..."
if curl -f http://localhost:11434/api/version >/dev/null 2>&1; then
    print_status "Ollama is running!"

    # Check if model is installed
    if docker exec jps-ollama ollama list | grep -q "qwen3:latest"; then
        print_status "qwen3:latest model is installed and ready!"
    else
        print_warning "qwen3:latest model is being downloaded. This may take several minutes..."
        print_status "You can check progress with: docker-compose logs -f ollama"
    fi
else
    print_warning "Ollama is still starting up. Check logs with: docker-compose logs ollama"
fi

# Display access information
echo
print_status "=== JPS Prospect Aggregate is running! ==="
echo
echo "Access the application:"
echo "  Web Interface: http://localhost:5001"
echo "  Ollama API: http://localhost:11434"
echo
echo "Useful commands:"
echo "  View logs: docker-compose logs -f"
echo "  Stop services: docker-compose down"
echo "  Restart services: docker-compose restart"
echo "  View service status: docker-compose ps"
echo
echo "First time setup:"
echo "  1. The database will be automatically initialized"
echo "  2. A super admin user will be created (check logs for credentials)"
echo "  3. The qwen3 model will be downloaded (this may take time)"
echo

# Offer to show logs
read -p "Would you like to view the logs now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker-compose logs -f
fi
