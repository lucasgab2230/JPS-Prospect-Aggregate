# JPS Prospect Aggregate - PowerShell Launcher
# Full-featured Windows launcher with complete parity to launch.sh
# Requires PowerShell 5.0+ (included in Windows 10/11)

#Requires -Version 5.0

param(
    [Parameter(Position=0)]
    [ValidateSet('--dev', '--prod', '--quick', '--check', '--help', '-h', '--version', '-v')]
    [string]$Mode = ''
)

# Set console colors and title
$Host.UI.RawUI.WindowTitle = "JPS Prospect Aggregate Launcher"
$ErrorActionPreference = "Stop"

# Script version
$SCRIPT_VERSION = "2.0.0"

# Get project root
$PROJECT_ROOT = $PSScriptRoot

# ============================================================
# HELPER FUNCTIONS
# ============================================================

function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

function Write-Success {
    param([string]$Message)
    Write-ColorOutput "✅ $Message" "Green"
}

function Write-Error {
    param([string]$Message)
    Write-ColorOutput "❌ $Message" "Red"
}

function Write-Warning {
    param([string]$Message)
    Write-ColorOutput "⚠️  $Message" "Yellow"
}

function Write-Info {
    param([string]$Message)
    Write-ColorOutput "ℹ️  $Message" "Cyan"
}

function Write-Header {
    param([string]$Title)
    Write-Host ""
    Write-ColorOutput ("=" * 60) "Blue"
    Write-ColorOutput "  $Title" "Blue"
    Write-ColorOutput ("=" * 60) "Blue"
    Write-Host ""
}

function Show-Banner {
    Clear-Host
    Write-ColorOutput @"

     ██╗██████╗ ███████╗    ██╗      █████╗ ██╗   ██╗███╗   ██╗ ██████╗██╗  ██╗███████╗██████╗
     ██║██╔══██╗██╔════╝    ██║     ██╔══██╗██║   ██║████╗  ██║██╔════╝██║  ██║██╔════╝██╔══██╗
     ██║██████╔╝███████╗    ██║     ███████║██║   ██║██╔██╗ ██║██║     ███████║█████╗  ██████╔╝
██   ██║██╔═══╝ ╚════██║    ██║     ██╔══██║██║   ██║██║╚██╗██║██║     ██╔══██║██╔══╝  ██╔══██╗
╚█████╔╝██║     ███████║    ███████╗██║  ██║╚██████╔╝██║ ╚████║╚██████╗██║  ██║███████╗██║  ██║
 ╚════╝ ╚═╝     ╚══════╝    ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝

"@ -ForegroundColor Cyan

    Write-ColorOutput "                    JPS Prospect Aggregate - PowerShell Launcher v$SCRIPT_VERSION" "White"
    Write-ColorOutput "                           Simplifying Your Development Workflow" "Gray"
    Write-Host ""
}

function Test-Command {
    param([string]$Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

function Prompt-User {
    param(
        [string]$Message,
        [string]$Default = ""
    )

    if ($Default) {
        $prompt = "$Message [$Default]: "
    } else {
        $prompt = "${Message}: "
    }

    $response = Read-Host $prompt
    if ([string]::IsNullOrWhiteSpace($response) -and $Default) {
        return $Default
    }
    return $response
}

function Confirm-Action {
    param(
        [string]$Message,
        [string]$Default = "n"
    )

    $response = Prompt-User "$Message (y/n)" $Default
    return $response -match '^[Yy]'
}

# ============================================================
# PREREQUISITES CHECKING
# ============================================================

function Test-Python {
    Write-Info "Checking Python installation..."

    $pythonCommands = @("python", "python3", "python3.12", "python3.11")
    $pythonCmd = $null
    $pythonVersion = $null

    foreach ($cmd in $pythonCommands) {
        if (Test-Command $cmd) {
            $versionOutput = & $cmd --version 2>&1
            if ($versionOutput -match "Python (\d+)\.(\d+)\.(\d+)") {
                $major = [int]$Matches[1]
                $minor = [int]$Matches[2]

                if ($major -eq 3 -and $minor -ge 11) {
                    $pythonCmd = $cmd
                    $pythonVersion = "$major.$minor.$($Matches[3])"
                    break
                }
            }
        }
    }

    if ($pythonCmd) {
        Write-Success "Python $pythonVersion found ($pythonCmd)"

        # Check for conda environment
        $condaEnv = $env:CONDA_DEFAULT_ENV
        if ($condaEnv) {
            Write-Info "Conda environment active: $condaEnv"
            if ($condaEnv -eq "base") {
                Write-Warning "Using conda base environment - consider activating a project environment"
            }
        }

        return $pythonCmd
    } else {
        Write-Error "Python 3.11+ not found"
        Write-Info "Please install Python from https://www.python.org/"
        return $null
    }
}

function Test-Node {
    Write-Info "Checking Node.js installation..."

    if (Test-Command "node") {
        $nodeVersion = & node --version 2>&1
        if ($nodeVersion -match "v(\d+)") {
            $majorVersion = [int]$Matches[1]
            if ($majorVersion -ge 20) {
                Write-Success "Node.js $nodeVersion found"

                if (Test-Command "npm") {
                    $npmVersion = & npm --version 2>&1
                    Write-Success "npm $npmVersion found"
                    return $true
                } else {
                    Write-Error "npm not found"
                    return $false
                }
            } else {
                Write-Warning "Node.js $nodeVersion found, but version 20+ recommended"
                return $true
            }
        }
    }

    Write-Error "Node.js not found"
    Write-Info "Please install Node.js from https://nodejs.org/"
    return $false
}

function Test-Docker {
    Write-Info "Checking Docker installation..."

    if (Test-Command "docker") {
        $dockerVersion = & docker --version 2>&1
        Write-Success "Docker found: $dockerVersion"

        # Check if Docker daemon is running
        try {
            & docker ps 2>&1 | Out-Null
            Write-Success "Docker daemon is running"

            # Check Docker Compose
            if (Test-Command "docker-compose") {
                Write-Success "Docker Compose found"
            } else {
                # Try docker compose (v2)
                & docker compose version 2>&1 | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "Docker Compose (v2) found"
                } else {
                    Write-Warning "Docker Compose not found"
                }
            }
            return $true
        } catch {
            Write-Warning "Docker daemon is not running"
            Write-Info "Please start Docker Desktop"
            return $false
        }
    } else {
        Write-Warning "Docker not found (required for production mode)"
        Write-Info "Install from https://www.docker.com/products/docker-desktop/"
        return $false
    }
}

function Test-Ollama {
    Write-Info "Checking Ollama installation..."

    if (Test-Command "ollama") {
        $ollamaVersion = & ollama --version 2>&1
        Write-Success "Ollama found: $ollamaVersion"

        # Check if qwen3 model is available
        $models = & ollama list 2>&1
        if ($models -match "qwen3:latest") {
            Write-Success "qwen3:latest model found"
        } else {
            Write-Warning "qwen3:latest model not found"
            Write-Info "Pull it with: ollama pull qwen3:latest"
        }
        return $true
    } else {
        Write-Warning "Ollama not found (required for LLM features)"
        Write-Info "Install from https://ollama.ai/"
        return $false
    }
}

function Test-Prerequisites {
    Write-Header "Checking Prerequisites"

    $pythonCmd = Test-Python
    $hasNode = Test-Node
    $hasDocker = Test-Docker
    $hasOllama = Test-Ollama

    if (-not $pythonCmd -or -not $hasNode) {
        Write-Error "Missing required prerequisites"
        return $null
    }

    Write-Success "All required prerequisites found!"
    return $pythonCmd
}

# ============================================================
# ENVIRONMENT CONFIGURATION
# ============================================================

function Get-CurrentEnvironment {
    if (Test-Path "$PROJECT_ROOT\.env") {
        $content = Get-Content "$PROJECT_ROOT\.env" -Raw
        if ($content -match "ENVIRONMENT=(\w+)") {
            return $Matches[1]
        }
    }
    return "none"
}

function Configure-Environment {
    param(
        [string]$Mode = "development"
    )

    $envPath = "$PROJECT_ROOT\.env"

    # Check if .env exists and has the right environment
    if (Test-Path $envPath) {
        $currentEnv = Get-CurrentEnvironment
        if ($currentEnv -eq $Mode) {
            Write-Success "Using existing $Mode configuration"
            return $true
        }
    }

    Write-Info "Creating $Mode configuration..."

    # Preserve existing values if available
    $existingSecret = ""
    $existingDomain = ""
    $existingCloudflare = ""

    if (Test-Path $envPath) {
        $content = Get-Content $envPath -Raw
        if ($content -match "SECRET_KEY=(.+)") { $existingSecret = $Matches[1] }
        if ($content -match "PRODUCTION_DOMAIN=(.+)") { $existingDomain = $Matches[1] }
        if ($content -match "CLOUDFLARE_TUNNEL_TOKEN=(.+)") { $existingCloudflare = $Matches[1] }
    }

    # Generate or preserve SECRET_KEY
    $secretKey = $existingSecret
    if ([string]::IsNullOrWhiteSpace($secretKey)) {
        $secretKey = -join ((1..64) | ForEach {'{0:x}' -f (Get-Random -Max 16)})
    }

    # Base configuration
    $envContent = @"
# JPS Prospect Aggregate - $($Mode.ToUpper()) Environment
# Generated by launcher on $(Get-Date)

ENVIRONMENT=$Mode
SECRET_KEY=$secretKey
FLASK_APP=run.py

# Database paths are NOT set here - the app will use relative paths
# and convert them to absolute at runtime for portability
# DATABASE_URL=  # DO NOT SET - leave commented
# USER_DATABASE_URL=  # DO NOT SET - leave commented

"@

    if ($Mode -eq "development") {
        $envContent += @"
# Development Settings
DEBUG=True
FLASK_ENV=development
LOG_LEVEL=DEBUG
HOST=127.0.0.1
PORT=5001

# Frontend
VITE_API_URL=http://localhost:5001
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5001,http://127.0.0.1:3000,http://127.0.0.1:5001

# Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:latest

# Features
ENABLE_LLM_ENHANCEMENT=True
ENABLE_DUPLICATE_DETECTION=True
FILE_FRESHNESS_SECONDS=86400

# Performance
WORKERS=1
TIMEOUT=300
"@
    } else {
        # Production mode - handle domain
        $domain = $existingDomain
        if (-not [string]::IsNullOrWhiteSpace($existingDomain)) {
            Write-Info "Current domain: $existingDomain"
            if (-not (Confirm-Action "Keep existing domain?" "y")) {
                $domain = Prompt-User "Enter new production domain (e.g., app.example.com)"
                if ([string]::IsNullOrWhiteSpace($domain)) {
                    Write-Error "Domain is required for production"
                    return $false
                }
            }
        } else {
            $domain = Prompt-User "Enter your production domain (e.g., app.example.com)"
            if ([string]::IsNullOrWhiteSpace($domain)) {
                Write-Error "Domain is required for production"
                return $false
            }
        }

        # Cloudflare tunnel (optional)
        $cloudflareToken = $existingCloudflare
        if (-not [string]::IsNullOrWhiteSpace($existingCloudflare)) {
            Write-Info "Cloudflare tunnel is currently configured"
            if (-not (Confirm-Action "Keep existing Cloudflare token?" "y")) {
                if (Confirm-Action "Remove Cloudflare tunnel?" "n") {
                    $cloudflareToken = ""
                } else {
                    $cloudflareToken = Prompt-User "Enter new Cloudflare tunnel token"
                }
            }
        } else {
            if (Confirm-Action "Configure Cloudflare tunnel?" "n") {
                $cloudflareToken = Prompt-User "Enter Cloudflare tunnel token"
            }
        }

        $envContent += @"
# Production Settings
PRODUCTION_DOMAIN=$domain
DEBUG=False
FLASK_ENV=production
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=5001

# Security
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax

# CORS & Frontend
ALLOWED_ORIGINS=https://$domain,http://localhost:3000,http://localhost:5001
VITE_API_URL=https://$domain

# Ollama (Docker)
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen3:latest

# Cloudflare
CLOUDFLARE_TUNNEL_TOKEN=$cloudflareToken

# Features
ENABLE_LLM_ENHANCEMENT=True
ENABLE_DUPLICATE_DETECTION=True
FILE_FRESHNESS_SECONDS=86400

# Performance
WORKERS=12
TIMEOUT=120
"@
    }

    # Write the .env file
    Set-Content -Path $envPath -Value $envContent -Encoding UTF8
    Write-Success "$Mode configuration created"
    return $true
}

# ============================================================
# DEVELOPMENT MODE
# ============================================================

function Install-PythonDependencies {
    param([string]$PythonCmd)

    Write-Info "Checking Python dependencies..."

    if (-not (Test-Path "$PROJECT_ROOT\requirements.txt")) {
        Write-Error "requirements.txt not found"
        return $false
    }

    # Check if packages need to be installed
    $installedPackages = & $PythonCmd -m pip list --format=freeze 2>&1
    $requiredPackages = Get-Content "$PROJECT_ROOT\requirements.txt"

    $needsInstall = $false
    foreach ($req in $requiredPackages) {
        if ($req -and -not ($req -match "^#") -and -not ($installedPackages -match $req.Split("==")[0])) {
            $needsInstall = $true
            break
        }
    }

    if ($needsInstall) {
        Write-Info "Installing Python packages..."
        & $PythonCmd -m pip install -r "$PROJECT_ROOT\requirements.txt"
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Python packages installed"

            # Install Playwright browsers if needed
            if (Test-Command "playwright") {
                Write-Info "Installing Playwright browsers..."
                & playwright install chromium
            }
        } else {
            Write-Error "Failed to install Python packages"
            return $false
        }
    } else {
        Write-Success "Python packages ready"
    }

    return $true
}

function Setup-Frontend {
    Write-Info "Checking frontend..."

    if (-not (Test-Path "$PROJECT_ROOT\frontend-react")) {
        Write-Error "frontend-react directory not found"
        return $false
    }

    Push-Location "$PROJECT_ROOT\frontend-react"

    try {
        if (-not (Test-Path "node_modules")) {
            Write-Info "Installing frontend dependencies (first time setup)..."
            & npm install
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Frontend packages installed"
            } else {
                Write-Error "Failed to install frontend packages"
                return $false
            }
        } else {
            Write-Success "Frontend packages ready"
        }
        return $true
    } finally {
        Pop-Location
    }
}

function Setup-Databases {
    param([string]$PythonCmd)

    Write-Info "Checking databases..."

    # Create data directory if it doesn't exist
    if (-not (Test-Path "$PROJECT_ROOT\data")) {
        New-Item -ItemType Directory -Path "$PROJECT_ROOT\data" | Out-Null
    }

    # Check if databases exist
    $needsInit = $false
    if (-not (Test-Path "$PROJECT_ROOT\data\jps_aggregate.db") -or
        -not (Test-Path "$PROJECT_ROOT\data\jps_users.db")) {
        $needsInit = $true
    }

    if ($needsInit) {
        Write-Info "Initializing databases (first time setup)..."

        if (Test-Path "$PROJECT_ROOT\scripts\setup_databases.py") {
            & $PythonCmd "$PROJECT_ROOT\scripts\setup_databases.py"
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Databases initialized"
            } else {
                Write-Error "Failed to initialize databases"
                return $false
            }
        } else {
            # Fallback: run migrations
            $env:FLASK_APP = "run.py"
            & $PythonCmd -m flask db upgrade
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Database migrations completed"
            } else {
                Write-Error "Failed to run migrations"
                return $false
            }
        }
    } else {
        Write-Success "Databases ready"
    }

    return $true
}

function Test-Port {
    param([int]$Port)

    $tcpConnection = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    return $null -eq $tcpConnection
}

function Start-DevelopmentServers {
    param([string]$PythonCmd)

    Write-Header "Starting Development Servers"

    # Check port availability
    $backendPort = 5001
    $frontendPort = 3000

    if (-not (Test-Port $backendPort)) {
        Write-Warning "Port $backendPort is already in use"
        Write-Info "You may need to kill the existing process"
    }

    if (-not (Test-Port $frontendPort)) {
        Write-Warning "Port $frontendPort is already in use"
        Write-Info "You may need to kill the existing process"
    }

    # Create launcher state directory
    $launcherDir = "$PROJECT_ROOT\.launcher"
    if (-not (Test-Path $launcherDir)) {
        New-Item -ItemType Directory -Path $launcherDir | Out-Null
    }

    # Start backend
    Write-Info "Starting backend server on port $backendPort..."
    $backendProcess = Start-Process -FilePath $PythonCmd -ArgumentList "run.py" `
        -WorkingDirectory $PROJECT_ROOT `
        -RedirectStandardOutput "$launcherDir\backend.log" `
        -RedirectStandardError "$launcherDir\backend.error.log" `
        -WindowStyle Hidden `
        -PassThru

    if ($backendProcess) {
        Set-Content -Path "$launcherDir\backend.pid" -Value $backendProcess.Id
        Write-Success "Backend server started (PID: $($backendProcess.Id))"
    } else {
        Write-Error "Failed to start backend server"
        return $false
    }

    # Start frontend
    Write-Info "Starting frontend server on port $frontendPort..."
    $frontendProcess = Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c", "npm run dev" `
        -WorkingDirectory "$PROJECT_ROOT\frontend-react" `
        -RedirectStandardOutput "$launcherDir\frontend.log" `
        -RedirectStandardError "$launcherDir\frontend.error.log" `
        -WindowStyle Hidden `
        -PassThru

    if ($frontendProcess) {
        Set-Content -Path "$launcherDir\frontend.pid" -Value $frontendProcess.Id
        Write-Success "Frontend server started (PID: $($frontendProcess.Id))"
    } else {
        Write-Error "Failed to start frontend server"
        return $false
    }

    # Wait a moment for servers to start
    Start-Sleep -Seconds 3

    # Open browser
    Write-Info "Opening browser..."
    Start-Process "http://localhost:$frontendPort"

    Write-Success "Development servers are running!"
    Write-Info "Backend: http://localhost:$backendPort"
    Write-Info "Frontend: http://localhost:$frontendPort"

    # Show useful commands
    Write-Header "Useful Commands"
    Write-Host "📋 Development Commands:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  View Logs:"
    Write-Host "    Get-Content $launcherDir\backend.log -Tail 50"
    Write-Host "    Get-Content $launcherDir\frontend.log -Tail 50"
    Write-Host ""
    Write-Host "  Stop Servers:"
    Write-Host "    Stop-Process -Id (Get-Content $launcherDir\backend.pid)"
    Write-Host "    Stop-Process -Id (Get-Content $launcherDir\frontend.pid)"
    Write-Host ""
    Write-Host "  Run Scrapers:"
    Write-Host "    python scripts\run_all_scrapers.py"
    Write-Host "    python -m scripts.scrapers.run_scraper --source `"DHS`""
    Write-Host ""
    Write-Host "💡 Tips:" -ForegroundColor Cyan
    Write-Host "  • Press Ctrl+C to stop servers"
    Write-Host "  • Logs are in: $launcherDir\"
    Write-Host ""

    return $true
}

function Start-Development {
    param([string]$PythonCmd)

    Write-Header "Starting Development Mode"

    # Configure environment for development
    if (-not (Configure-Environment "development")) {
        return $false
    }

    # Setup everything
    if (-not (Install-PythonDependencies $PythonCmd)) { return $false }
    if (-not (Setup-Frontend)) { return $false }
    if (-not (Setup-Databases $PythonCmd)) { return $false }
    if (-not (Start-DevelopmentServers $PythonCmd)) { return $false }

    Write-Info "Press any key to stop servers..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

    # Stop servers
    Stop-Servers

    return $true
}

# ============================================================
# PRODUCTION MODE
# ============================================================

function Start-Production {
    Write-Header "Production Mode Setup"

    # Configure environment for production
    if (-not (Configure-Environment "production")) {
        return $false
    }

    # Check Docker
    if (-not (Test-Docker)) {
        Write-Error "Docker is required for production mode"
        return $false
    }

    # Build Docker images
    Write-Info "Building Docker images..."
    & docker-compose build
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to build Docker images"
        return $false
    }
    Write-Success "Docker images built"

    # Check for Cloudflare token
    $envContent = Get-Content "$PROJECT_ROOT\.env" -Raw
    $useCloudflare = $envContent -match "CLOUDFLARE_TUNNEL_TOKEN=.+"

    # Start services
    if ($useCloudflare) {
        Write-Info "Starting services with Cloudflare tunnel..."
        & docker-compose --profile cloudflare up -d
    } else {
        Write-Info "Starting services..."
        & docker-compose up -d
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to start Docker services"
        return $false
    }

    Write-Success "Docker services started"

    # Wait for services
    Write-Info "Waiting for services to start..."
    Start-Sleep -Seconds 10

    # Check health
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:5001/health" -UseBasicParsing
        Write-Success "Application is healthy!"
    } catch {
        Write-Warning "Health check failed - checking logs..."
        & docker-compose logs --tail=50 web
    }

    # Display status
    Write-Header "Deployment Status"
    & docker-compose ps

    # Show commands
    Write-Header "Useful Commands"
    Write-Host "📋 Production Commands:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  View logs:        docker-compose logs -f web"
    Write-Host "  Stop application: docker-compose down"
    Write-Host "  Restart:          docker-compose restart"
    Write-Host "  Database backup:  docker exec jps-web sqlite3 /app/data/jps_aggregate.db '.backup /app/backups/backup.db'"
    Write-Host ""

    if ($useCloudflare) {
        $domain = $envContent -match "PRODUCTION_DOMAIN=(.+)" | Out-Null; $Matches[1]
        Write-Info "Application should be accessible at: https://$domain"
    } else {
        Write-Info "Application is running at: http://localhost:5001"
        Write-Info "Configure your reverse proxy to point to port 5001"
    }

    return $true
}

# ============================================================
# QUICK START MODE
# ============================================================

function Start-QuickMode {
    param([string]$PythonCmd)

    Write-Header "Quick Start"

    $currentEnv = Get-CurrentEnvironment

    if ($currentEnv -eq "production") {
        Write-Info "Detected production environment"
        return Start-Production
    } else {
        Write-Info "Starting in development mode"
        return Start-Development $PythonCmd
    }
}

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

function Stop-Servers {
    Write-Info "Stopping servers..."

    $launcherDir = "$PROJECT_ROOT\.launcher"

    # Stop backend
    if (Test-Path "$launcherDir\backend.pid") {
        $pid = Get-Content "$launcherDir\backend.pid"
        try {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Success "Backend server stopped"
        } catch {
            Write-Warning "Backend server already stopped"
        }
        Remove-Item "$launcherDir\backend.pid" -Force
    }

    # Stop frontend
    if (Test-Path "$launcherDir\frontend.pid") {
        $pid = Get-Content "$launcherDir\frontend.pid"
        try {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Success "Frontend server stopped"
        } catch {
            Write-Warning "Frontend server already stopped"
        }
        Remove-Item "$launcherDir\frontend.pid" -Force
    }
}

function Show-Help {
    Write-Header "JPS Launcher Help"
    Write-Host "Usage: .\launch.ps1 [option]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  --help, -h      Show this help message"
    Write-Host "  --version, -v   Show version information"
    Write-Host "  --dev           Start development mode directly"
    Write-Host "  --prod          Start production mode directly"
    Write-Host "  --quick         Quick start with auto-detection"
    Write-Host "  --check         Check prerequisites only"
    Write-Host ""
    Write-Host "Without options, the interactive menu will be shown."
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\launch.ps1 --dev    # Start development environment"
    Write-Host "  .\launch.ps1 --prod   # Start production with Docker"
    Write-Host "  .\launch.ps1          # Show interactive menu"
}

function Show-MainMenu {
    param([string]$PythonCmd)

    while ($true) {
        Show-Banner

        # Show current environment
        $currentEnv = Get-CurrentEnvironment
        if ($currentEnv -ne "none") {
            Write-Info "Current environment: $currentEnv"
        }

        Write-Header "Main Menu"
        Write-Host "  [1] Development Mode (Local)"
        Write-Host "  [2] Production Mode (Docker)"
        Write-Host "  [3] Quick Start (Auto-detect)"
        Write-Host "  [4] Check Prerequisites"
        Write-Host "  [5] Exit"
        Write-Host ""

        $choice = Read-Host "Select option [3]"
        if ([string]::IsNullOrWhiteSpace($choice)) {
            $choice = "3"
        }

        switch ($choice) {
            "1" {
                Start-Development $PythonCmd
                Write-Host ""
                Read-Host "Press Enter to continue"
            }
            "2" {
                Start-Production
                Write-Host ""
                Read-Host "Press Enter to continue"
            }
            "3" {
                Start-QuickMode $PythonCmd
                Write-Host ""
                Read-Host "Press Enter to continue"
            }
            "4" {
                Test-Prerequisites | Out-Null
                Write-Host ""
                Read-Host "Press Enter to continue"
            }
            "5" {
                Write-Info "Goodbye!"
                return
            }
            default {
                Write-Error "Invalid option"
                Start-Sleep -Seconds 2
            }
        }
    }
}

# ============================================================
# MAIN ENTRY POINT
# ============================================================

# Handle command-line arguments
switch ($Mode) {
    '--help' { Show-Help; exit 0 }
    '-h' { Show-Help; exit 0 }
    '--version' { Write-Host "JPS Launcher version $SCRIPT_VERSION"; exit 0 }
    '-v' { Write-Host "JPS Launcher version $SCRIPT_VERSION"; exit 0 }
    '--check' {
        Show-Banner
        $pythonCmd = Test-Prerequisites
        if ($pythonCmd) { exit 0 } else { exit 1 }
    }
    '--dev' {
        Show-Banner
        $pythonCmd = Test-Prerequisites
        if (-not $pythonCmd) { exit 1 }
        if (Start-Development $pythonCmd) { exit 0 } else { exit 1 }
    }
    '--prod' {
        Show-Banner
        Test-Prerequisites | Out-Null
        if (Start-Production) { exit 0 } else { exit 1 }
    }
    '--quick' {
        Show-Banner
        $pythonCmd = Test-Prerequisites
        if (-not $pythonCmd) { exit 1 }
        if (Start-QuickMode $pythonCmd) { exit 0 } else { exit 1 }
    }
    default {
        # Interactive mode
        $pythonCmd = Test-Prerequisites
        if (-not $pythonCmd) {
            Write-Error "Prerequisites check failed"
            Write-Info "Please install missing dependencies and try again"
            Read-Host "Press Enter to exit"
            exit 1
        }
        Show-MainMenu $pythonCmd
    }
}
