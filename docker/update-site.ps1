# Quick Update Script for Windows
# Double-click this file to update your site with latest changes

Write-Host "`n=== JPS Prospect Aggregate - Site Updater ===" -ForegroundColor Cyan
Write-Host "This will update your site with the latest changes from GitHub" -ForegroundColor Yellow
Write-Host ""

# Confirm before proceeding
$confirm = Read-Host "Do you want to update the site now? (Y/N)"
if ($confirm -ne 'Y' -and $confirm -ne 'y') {
    Write-Host "Update cancelled." -ForegroundColor Yellow
    pause
    exit
}

# Navigate to project directory
$projectPath = "C:\Docker\JPS-Prospect-Aggregate"
if (-not (Test-Path $projectPath)) {
    Write-Host "Error: Project directory not found at $projectPath" -ForegroundColor Red
    Write-Host "Please update the path in this script." -ForegroundColor Yellow
    pause
    exit 1
}

Set-Location $projectPath

# Check if Docker is running
Write-Host "`nChecking Docker Desktop..." -ForegroundColor Yellow
docker version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Desktop is not running! Please start it first." -ForegroundColor Red
    pause
    exit 1
}

# Pull latest code
Write-Host "`nPulling latest code from GitHub..." -ForegroundColor Yellow
git pull origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to pull latest code. Check your internet connection." -ForegroundColor Red
    pause
    exit 1
}

# Run deployment
Write-Host "`nStarting deployment..." -ForegroundColor Yellow
Write-Host "This will:" -ForegroundColor White
Write-Host "  1. Show maintenance page to users" -ForegroundColor Gray
Write-Host "  2. Backup your databases" -ForegroundColor Gray
Write-Host "  3. Update the application" -ForegroundColor Gray
Write-Host "  4. Run database migrations" -ForegroundColor Gray
Write-Host "  5. Restore service" -ForegroundColor Gray
Write-Host ""

# Execute deployment script
& ".\docker\deploy.ps1"

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n=== Update Complete! ===" -ForegroundColor Green
    Write-Host "Your site has been successfully updated." -ForegroundColor Green
    Write-Host "URL: http://localhost:5001" -ForegroundColor Cyan
} else {
    Write-Host "`n=== Update Failed ===" -ForegroundColor Red
    Write-Host "Please check the error messages above." -ForegroundColor Red
    Write-Host "You can check logs with: docker logs jps-web" -ForegroundColor Yellow
}

Write-Host "`nPress any key to close this window..."
pause
