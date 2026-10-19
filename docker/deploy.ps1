# PowerShell deployment script for Windows
param(
    [switch]$SkipBackup = $false,
    [switch]$SkipMaintenance = $false
)

# Colors for output
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

Write-ColorOutput Yellow "Starting deployment process..."

# Function to show maintenance page
function Enable-Maintenance {
    if (-not $SkipMaintenance) {
        Write-ColorOutput Yellow "Enabling maintenance mode..."
        docker run -d --name maintenance-page `
            -p 5001:80 `
            --network jps-network `
            -v "${PWD}\docker\maintenance.html:/usr/share/nginx/html/index.html:ro" `
            nginx:alpine 2>$null
    }
}

# Function to disable maintenance page
function Disable-Maintenance {
    if (-not $SkipMaintenance) {
        Write-ColorOutput Yellow "Disabling maintenance mode..."
        docker rm -f maintenance-page 2>$null | Out-Null
    }
}

# Function to backup databases
function Backup-Databases {
    if (-not $SkipBackup) {
        Write-ColorOutput Yellow "Backing up databases before deployment..."
        docker exec jps-backup /backup.sh
        if ($LASTEXITCODE -ne 0) {
            Write-ColorOutput Red "Backup failed! Aborting deployment."
            exit 1
        }
    }
}

# Function to run migrations
function Run-Migrations {
    Write-ColorOutput Yellow "Running database migrations..."
    docker exec jps-web alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        Write-ColorOutput Red "Migrations failed! Check logs with: docker logs jps-web"
        exit 1
    }
}

# Main deployment process
function Start-Deployment {
    # Check Docker is running
    docker version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-ColorOutput Red "Docker is not running! Please start Docker Desktop."
        exit 1
    }

    # Enable maintenance mode
    Enable-Maintenance

    # Backup databases
    Backup-Databases

    # Pull latest images
    Write-ColorOutput Yellow "Pulling latest images..."
    docker-compose pull

    # Build new image
    Write-ColorOutput Yellow "Building application image..."
    docker-compose build web

    # Stop current web container
    Write-ColorOutput Yellow "Stopping current web container..."
    docker-compose stop web

    # Start new web container
    Write-ColorOutput Yellow "Starting new web container..."
    docker-compose up -d web

    # Wait for web to be healthy
    Write-ColorOutput Yellow "Waiting for application to be ready..."
    $attempts = 0
    $maxAttempts = 30

    while ($attempts -lt $maxAttempts) {
        Start-Sleep -Seconds 2
        try {
            $response = Invoke-WebRequest -Uri http://localhost:5001/health -UseBasicParsing -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                break
            }
        }
        catch {
            $attempts++
            if ($attempts -eq $maxAttempts) {
                Write-ColorOutput Red "Application failed to start! Check logs with: docker logs jps-web"
                exit 1
            }
        }
    }

    # Run migrations
    Run-Migrations

    # Disable maintenance mode
    Disable-Maintenance

    # Final health check
    try {
        $response = Invoke-WebRequest -Uri http://localhost:5001/health -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-ColorOutput Green "Deployment completed successfully!"
            Write-Output "Application is running at: http://localhost:5001"
        }
    }
    catch {
        Write-ColorOutput Red "Health check failed! Check logs with: docker logs jps-web"
        exit 1
    }
}

# Run deployment
Start-Deployment
