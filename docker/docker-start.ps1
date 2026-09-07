# Docker startup script for Windows
# This script ensures a smooth Docker deployment on Windows systems

# Requires PowerShell to be run as Administrator for best results
# Set execution policy if needed: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

$ErrorActionPreference = "Stop"

# Colors for output
function Write-Success {
    param($Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-Error-Message {
    param($Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-Warning-Message {
    param($Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

# Function to check if command exists
function Test-CommandExists {
    param($Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

# Check prerequisites
Write-Success "Checking prerequisites..."

# Check for Docker
if (-not (Test-CommandExists "docker")) {
    Write-Error-Message "Docker is not installed or not in PATH."
    Write-Host "Please install Docker Desktop for Windows:"
    Write-Host "https://docs.docker.com/desktop/install/windows-install/"
    exit 1
}

# Check for Docker Compose
if (-not (Test-CommandExists "docker-compose")) {
    Write-Error-Message "Docker Compose is not installed or not in PATH."
    Write-Host "Docker Compose should be included with Docker Desktop."
    Write-Host "Try 'docker compose' instead of 'docker-compose'"
    exit 1
}

# Check if Docker daemon is running
try {
    docker info | Out-Null
} catch {
    Write-Error-Message "Docker daemon is not running. Please start Docker Desktop."
    exit 1
}

Write-Success "Prerequisites check passed!"

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Warning-Message ".env file not found. Creating from .env.example..."
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Success ".env file created. Please edit it with your configuration."
        Write-Warning-Message "Required configurations:"
        Write-Host "  - Set ENVIRONMENT=production"
        Write-Host "  - Generate and set SECRET_KEY if needed"
        Write-Host "  - Generate and set SECRET_KEY"
        Write-Host ""
        Write-Host "Generate SECRET_KEY with: python -c `"import secrets; print(secrets.token_hex(32))`""
        Write-Host ""
        Read-Host "Press Enter after updating .env file to continue"
    } else {
        Write-Error-Message ".env.example file not found. Cannot create .env file."
        exit 1
    }
}

# Validate .env file
Write-Success "Validating .env configuration..."
$envContent = Get-Content ".env" -Raw
if ($envContent -match "CHANGE_THIS") {
    Write-Error-Message "Please update the placeholder values in .env file"
    Write-Warning-Message "Look for CHANGE_THIS and replace with actual values"
    exit 1
}

# Create necessary directories
Write-Success "Creating necessary directories..."
$directories = @("data", "logs", "backups", "logs\error_screenshots", "logs\error_html")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

# Check for optional services
$composeProfiles = @()

# Check if Cloudflare token is set
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
if ($env:CLOUDFLARE_TUNNEL_TOKEN) {
    $composeProfiles += "cloudflare"
}

# Ask about Watchtower
$watchtowerResponse = Read-Host "Do you want to enable automatic container updates with Watchtower? (y/N)"
if ($watchtowerResponse -eq 'y' -or $watchtowerResponse -eq 'Y') {
    $composeProfiles += "full"
}

# Build profile string
$profileString = ""
if ($composeProfiles.Count -gt 0) {
    $profileString = "--profile " + ($composeProfiles -join " --profile ")
}

# Pull latest images
Write-Success "Pulling latest Docker images..."
if ($profileString) {
    Invoke-Expression "docker-compose $profileString pull"
} else {
    docker-compose pull
}

# Build the web service
Write-Success "Building web application image..."
docker-compose build --no-cache web

# Start services
Write-Success "Starting Docker containers..."
if ($profileString) {
    Invoke-Expression "docker-compose $profileString up -d"
} else {
    docker-compose up -d
}

# Wait for services to be healthy
Write-Success "Waiting for services to be healthy..."
Start-Sleep -Seconds 10

# Check service status
Write-Success "Checking service status..."
docker-compose ps

# Check if web service is responding
Write-Success "Checking web application..."
$maxAttempts = 30
$attempt = 1
$webReady = $false

while ($attempt -le $maxAttempts) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:5001/health" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $webReady = $true
            break
        }
    } catch {
        # Ignore errors and continue
    }

    Write-Host "." -NoNewline
    Start-Sleep -Seconds 2
    $attempt++
}

Write-Host "" # New line after dots

if ($webReady) {
    Write-Success "Web application is running!"
} else {
    Write-Error-Message "Web application failed to start after $maxAttempts attempts"
    Write-Success "Checking logs..."
    docker-compose logs --tail=50 web
    exit 1
}

# Check if Ollama is ready
Write-Success "Checking Ollama LLM service..."
try {
    $ollamaResponse = Invoke-WebRequest -Uri "http://localhost:11434/api/version" -UseBasicParsing -TimeoutSec 5
    if ($ollamaResponse.StatusCode -eq 200) {
        Write-Success "Ollama is running!"

        # Check if model is installed
        $modelList = docker exec jps-ollama ollama list 2>$null
        if ($modelList -match "qwen3:latest") {
            Write-Success "qwen3:latest model is installed and ready!"
        } else {
            Write-Warning-Message "qwen3:latest model is being downloaded. This may take several minutes..."
            Write-Success "You can check progress with: docker-compose logs -f ollama"
        }
    }
} catch {
    Write-Warning-Message "Ollama is still starting up. Check logs with: docker-compose logs ollama"
}

# Display access information
Write-Host ""
Write-Success "=== JPS Prospect Aggregate is running! ==="
Write-Host ""
Write-Host "Access the application:"
Write-Host "  Web Interface: http://localhost:5001"
Write-Host "  Ollama API: http://localhost:11434"
Write-Host ""
Write-Host "Useful commands:"
Write-Host "  View logs: docker-compose logs -f"
Write-Host "  Stop services: docker-compose down"
Write-Host "  Restart services: docker-compose restart"
Write-Host "  View service status: docker-compose ps"
Write-Host ""
Write-Host "First time setup:"
Write-Host "  1. The database will be automatically initialized"
Write-Host "  2. A super admin user will be created (check logs for credentials)"
Write-Host "  3. The qwen3 model will be downloaded (this may take time)"
Write-Host ""

# Offer to show logs
$logsResponse = Read-Host "Would you like to view the logs now? (y/N)"
if ($logsResponse -eq 'y' -or $logsResponse -eq 'Y') {
    docker-compose logs -f
}
