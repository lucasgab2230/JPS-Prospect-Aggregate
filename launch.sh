#!/bin/bash

# JPS Prospect Aggregate - Unified Launcher Script
# This script handles all setup, configuration, and deployment tasks
# Works on macOS, Linux, and Windows (via Git Bash/WSL)
# Version: 1.0.0

set -e  # Exit on error (we'll handle errors gracefully)

# ============================================================
# CONFIGURATION & CONSTANTS
# ============================================================

SCRIPT_VERSION="1.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
LAUNCHER_STATE_DIR="$PROJECT_ROOT/.launcher"
STATE_FILE="$LAUNCHER_STATE_DIR/state.json"
PREFERENCES_FILE="$LAUNCHER_STATE_DIR/preferences.json"
LOG_FILE="$LAUNCHER_STATE_DIR/launcher.log"

# Color codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Emoji indicators (can be disabled for terminals that don't support them)
CHECK_MARK="✅"
CROSS_MARK="❌"
WARNING_SIGN="⚠️"
ROCKET="🚀"
GEAR="⚙️"
PACKAGE="📦"
DATABASE="🗄️"
GLOBE="🌐"
LOCK="🔒"
SPARKLES="✨"
HOURGLASS="⏳"

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

# Initialize launcher state directory
init_launcher_state() {
    if [ ! -d "$LAUNCHER_STATE_DIR" ]; then
        mkdir -p "$LAUNCHER_STATE_DIR"
    fi

    # Initialize log file
    if [ ! -f "$LOG_FILE" ]; then
        touch "$LOG_FILE"
    fi
}

# Logging function
log_message() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
}

# Print colored output
print_color() {
    local color="$1"
    local message="$2"
    echo -e "${color}${message}${NC}"
}

# Print success message
print_success() {
    print_color "$GREEN" "$CHECK_MARK $1"
    log_message "SUCCESS" "$1"
}

# Print error message
print_error() {
    print_color "$RED" "$CROSS_MARK $1"
    log_message "ERROR" "$1"
}

# Print warning message
print_warning() {
    print_color "$YELLOW" "$WARNING_SIGN $1"
    log_message "WARNING" "$1"
}

# Print info message
print_info() {
    print_color "$CYAN" "ℹ️  $1"
    log_message "INFO" "$1"
}

# Print section header
print_header() {
    echo ""
    print_color "$BLUE" "============================================================"
    print_color "$BLUE" "  $1"
    print_color "$BLUE" "============================================================"
    echo ""
}

# Spinner for long operations
show_spinner() {
    local pid=$1
    local message=$2
    local spinner='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local i=0

    echo -n "$message "
    while kill -0 $pid 2>/dev/null; do
        i=$(( (i+1) %10 ))
        printf "\r$message ${spinner:$i:1}"
        sleep 0.1
    done
    printf "\r$message Done!\n"
}

# Progress bar
show_progress() {
    local current=$1
    local total=$2
    local width=50
    local percentage=$((current * 100 / total))
    local filled=$((current * width / total))

    printf "\r["
    printf "%${filled}s" | tr ' ' '='
    printf "%$((width - filled))s" | tr ' ' ' '
    printf "] %d%%" $percentage

    if [ $current -eq $total ]; then
        echo ""
    fi
}

# Prompt for user input
prompt_user() {
    local prompt="$1"
    local default="$2"
    local response

    if [ -n "$default" ]; then
        read -p "$prompt [$default]: " response
        response="${response:-$default}"
    else
        read -p "$prompt: " response
    fi

    echo "$response"
}

# Yes/No prompt
confirm() {
    local prompt="$1"
    local default="${2:-n}"
    local response

    if [ "$default" = "y" ]; then
        read -p "$prompt (Y/n): " -n 1 -r response
    else
        read -p "$prompt (y/N): " -n 1 -r response
    fi
    echo

    if [ -z "$response" ]; then
        response="$default"
    fi

    [[ "$response" =~ ^[Yy]$ ]]
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# ============================================================
# OS DETECTION
# ============================================================

detect_os() {
    local os_type=""
    local os_name=""

    case "$(uname -s)" in
        Darwin*)
            os_type="macos"
            os_name="macOS"
            # Detect Apple Silicon vs Intel
            if [[ $(uname -m) == "arm64" ]]; then
                os_name="macOS (Apple Silicon)"
            else
                os_name="macOS (Intel)"
            fi
            ;;
        Linux*)
            os_type="linux"
            if [ -f /etc/os-release ]; then
                . /etc/os-release
                os_name="$NAME"
            else
                os_name="Linux"
            fi
            ;;
        MINGW* | MSYS* | CYGWIN*)
            os_type="windows"
            os_name="Windows (Git Bash)"
            ;;
        *)
            os_type="unknown"
            os_name="Unknown"
            ;;
    esac

    export OS_TYPE="$os_type"
    export OS_NAME="$os_name"

    log_message "INFO" "Detected OS: $OS_NAME ($OS_TYPE)"
}

# Get the appropriate command for opening URLs
get_open_command() {
    case "$OS_TYPE" in
        macos)
            echo "open"
            ;;
        linux)
            if command_exists xdg-open; then
                echo "xdg-open"
            elif command_exists gnome-open; then
                echo "gnome-open"
            else
                echo ""
            fi
            ;;
        windows)
            echo "start"
            ;;
        *)
            echo ""
            ;;
    esac
}

# ============================================================
# PREREQUISITE CHECKING
# ============================================================

check_python() {
    print_info "Checking Python installation..."

    local python_cmd=""
    local python_version=""

    # Try different Python commands
    for cmd in python3 python python3.11 python3.12; do
        if command_exists "$cmd"; then
            python_version=$($cmd --version 2>&1 | cut -d' ' -f2)
            local major=$(echo $python_version | cut -d. -f1)
            local minor=$(echo $python_version | cut -d. -f2)

            if [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; then
                python_cmd="$cmd"
                break
            fi
        fi
    done

    if [ -z "$python_cmd" ]; then
        print_error "Python 3.11+ not found"
        print_info "Please install Python 3.11 or higher"

        case "$OS_TYPE" in
            macos)
                print_info "Install with: brew install python@3.11"
                ;;
            linux)
                print_info "Install with: sudo apt install python3.11 (Ubuntu/Debian)"
                print_info "           or: sudo yum install python3.11 (RHEL/CentOS)"
                ;;
            windows)
                print_info "Download from: https://www.python.org/downloads/"
                ;;
        esac

        return 1
    fi

    export PYTHON_CMD="$python_cmd"
    export PYTHON_VERSION="$python_version"
    print_success "Python $python_version found ($python_cmd)"

    # Check for virtual environment
    if [ -n "$VIRTUAL_ENV" ]; then
        print_info "Virtual environment active: $VIRTUAL_ENV"
    elif [ -n "$CONDA_DEFAULT_ENV" ]; then
        print_info "Conda environment active: $CONDA_DEFAULT_ENV"
    fi

    return 0
}

check_node() {
    print_info "Checking Node.js installation..."

    if ! command_exists node; then
        print_error "Node.js not found"
        print_info "Please install Node.js 20.x"

        case "$OS_TYPE" in
            macos)
                print_info "Install with: brew install node@20"
                ;;
            linux)
                print_info "Install with: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -"
                print_info "           then: sudo apt install nodejs"
                ;;
            windows)
                print_info "Download from: https://nodejs.org/"
                ;;
        esac

        return 1
    fi

    local node_version=$(node --version | cut -d'v' -f2)
    local major=$(echo $node_version | cut -d. -f1)

    if [ "$major" -lt 20 ]; then
        print_warning "Node.js version $node_version found, but 20.x is recommended"
    else
        print_success "Node.js $node_version found"
    fi

    if ! command_exists npm; then
        print_error "npm not found"
        return 1
    fi

    local npm_version=$(npm --version)
    print_success "npm $npm_version found"

    return 0
}

check_docker() {
    print_info "Checking Docker installation..."

    if ! command_exists docker; then
        print_warning "Docker not found (required for production mode)"
        return 1
    fi

    local docker_version=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
    print_success "Docker $docker_version found"

    # Check if Docker daemon is running
    if ! docker info >/dev/null 2>&1; then
        print_warning "Docker daemon is not running"
        print_info "Start Docker Desktop or run: sudo systemctl start docker"
        return 1
    fi

    # Check Docker Compose
    if command_exists docker-compose; then
        local compose_version=$(docker-compose --version | cut -d' ' -f3 | cut -d',' -f1)
        print_success "Docker Compose $compose_version found"
    elif docker compose version >/dev/null 2>&1; then
        print_success "Docker Compose (plugin) found"
    else
        print_warning "Docker Compose not found"
        return 1
    fi

    return 0
}

check_ollama() {
    print_info "Checking Ollama installation..."

    if ! command_exists ollama; then
        print_warning "Ollama not found (optional - for LLM features)"
        print_info "Install from: https://ollama.ai/"
        return 1
    fi

    local ollama_version=$(ollama --version | head -n1)
    print_success "Ollama found: $ollama_version"

    # Check if Ollama is running
    if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        print_warning "Ollama service is not running"
        print_info "Start with: ollama serve"
        return 1
    fi

    # Check for qwen3 model
    if ollama list 2>/dev/null | grep -q "qwen3:latest"; then
        print_success "qwen3:latest model found"
    else
        print_warning "qwen3:latest model not found"
        if confirm "Download qwen3:latest model (5.2GB)?"; then
            print_info "Downloading qwen3:latest..."
            ollama pull qwen3:latest
            print_success "Model downloaded successfully"
        fi
    fi

    return 0
}

check_git() {
    if ! command_exists git; then
        print_error "Git not found"
        return 1
    fi

    local git_version=$(git --version | cut -d' ' -f3)
    print_success "Git $git_version found"

    # Check if we're in a git repository
    if git rev-parse --git-dir >/dev/null 2>&1; then
        local branch=$(git branch --show-current)
        print_info "Git repository detected (branch: $branch)"
    fi

    return 0
}

check_prerequisites() {
    print_header "Checking Prerequisites"

    local all_good=true

    check_git || all_good=false
    check_python || all_good=false
    check_node || all_good=false

    # Docker is optional for development
    check_docker || print_info "Docker is optional for development mode"

    # Ollama is optional
    check_ollama || print_info "Ollama is optional (LLM features will be disabled)"

    if [ "$all_good" = false ]; then
        print_error "Some prerequisites are missing"
        return 1
    fi

    print_success "All required prerequisites found!"
    return 0
}

# ============================================================
# ENVIRONMENT MANAGEMENT
# ============================================================

detect_current_environment() {
    if [ -f "$PROJECT_ROOT/.env" ]; then
        local env_type=$(grep "^ENVIRONMENT=" "$PROJECT_ROOT/.env" | cut -d'=' -f2)
        echo "$env_type"
    else
        echo "none"
    fi
}

save_preference() {
    local key="$1"
    local value="$2"

    # Create preferences file if it doesn't exist
    if [ ! -f "$PREFERENCES_FILE" ]; then
        echo "{}" > "$PREFERENCES_FILE"
    fi

    # Update preference (simple implementation - could use jq if available)
    local temp_file="$PREFERENCES_FILE.tmp"
    if command_exists jq; then
        jq --arg key "$key" --arg value "$value" '.[$key] = $value' "$PREFERENCES_FILE" > "$temp_file"
        mv "$temp_file" "$PREFERENCES_FILE"
    else
        # Fallback without jq
        echo "$key=$value" >> "$PREFERENCES_FILE.simple"
    fi
}

get_preference() {
    local key="$1"
    local default="$2"

    if [ -f "$PREFERENCES_FILE" ] && command_exists jq; then
        local value=$(jq -r --arg key "$key" '.[$key] // empty' "$PREFERENCES_FILE")
        if [ -n "$value" ]; then
            echo "$value"
        else
            echo "$default"
        fi
    elif [ -f "$PREFERENCES_FILE.simple" ]; then
        grep "^$key=" "$PREFERENCES_FILE.simple" | cut -d'=' -f2 || echo "$default"
    else
        echo "$default"
    fi
}

# ============================================================
# DEVELOPMENT MODE SETUP
# ============================================================

setup_python_env() {
    print_info "Checking Python environment..."

    # Check if we're already in a virtual environment
    if [ -n "$VIRTUAL_ENV" ]; then
        print_success "Using virtual environment: $VIRTUAL_ENV"
    elif [ -n "$CONDA_DEFAULT_ENV" ]; then
        # Check if it's the base environment (which we should NOT use)
        if [ "$CONDA_DEFAULT_ENV" = "base" ]; then
            print_error "Cannot use conda base environment (system Python protected)"
            print_info "You have a conda environment 'jps_env' available"
            print_warning "Please activate it first:"
            echo ""
            echo "    conda activate jps_env"
            echo "    ./launch.sh --dev"
            echo ""
            print_info "Or the script can create a local venv instead"
            if confirm "Create a local virtual environment?" "y"; then
                print_info "Creating virtual environment..."
                $PYTHON_CMD -m venv venv
                if [ -f "venv/bin/activate" ]; then
                    source venv/bin/activate
                elif [ -f "venv/Scripts/activate" ]; then
                    source venv/Scripts/activate
                fi
                print_success "Virtual environment created and activated"
            else
                print_error "Cannot proceed without proper Python environment"
                print_info "Please run: conda activate jps_env"
                exit 1
            fi
        else
            print_success "Using conda environment: $CONDA_DEFAULT_ENV"
        fi
    else
        # Try to activate existing venv if it exists
        if [ -d "venv" ]; then
            if [ -f "venv/bin/activate" ]; then
                source venv/bin/activate
                print_success "Virtual environment activated"
            elif [ -f "venv/Scripts/activate" ]; then
                source venv/Scripts/activate
                print_success "Virtual environment activated"
            fi
        else
            # Suggest using conda env if available
            print_warning "No Python environment active"
            print_info "Recommended: conda activate jps_env"
            if confirm "Create a local virtual environment instead?" "y"; then
                print_info "Creating virtual environment..."
                $PYTHON_CMD -m venv venv
                if [ -f "venv/bin/activate" ]; then
                    source venv/bin/activate
                elif [ -f "venv/Scripts/activate" ]; then
                    source venv/Scripts/activate
                fi
                print_success "Virtual environment created and activated"
            else
                print_error "Cannot proceed without Python environment"
                print_info "Please run: conda activate jps_env"
                exit 1
            fi
        fi
    fi

    return 0
}

install_python_deps() {
    print_info "Checking Python dependencies..."

    if [ ! -f "requirements.txt" ]; then
        print_error "requirements.txt not found"
        return 1
    fi

    # Quick check - try importing key packages
    if $PYTHON_CMD -c "import flask, sqlalchemy, playwright" 2>/dev/null; then
        print_success "Python packages ready"
    else
        print_info "Installing missing Python packages..."

        # Try to install packages and check for success
        if $PYTHON_CMD -m pip install -r requirements.txt --quiet --disable-pip-version-check 2>/dev/null; then
            print_success "Python packages installed"
        else
            # Installation failed - likely due to PEP 668
            print_error "Failed to install Python packages"

            # Check if we're in base environment
            if [ "$CONDA_DEFAULT_ENV" = "base" ]; then
                print_error "Cannot install packages in conda base environment"
                print_warning "Please activate the proper environment first:"
                echo ""
                echo "    conda activate jps_env"
                echo "    ./launch.sh --dev"
                echo ""
                return 1
            else
                print_error "pip install failed - check error messages above"
                print_info "You may need to activate a proper Python environment"
                return 1
            fi
        fi

        # Install Playwright browsers if needed
        if command_exists playwright; then
            if ! [ -d "$HOME/.cache/ms-playwright" ] && ! [ -d "$HOME/Library/Caches/ms-playwright" ]; then
                print_info "Installing Playwright browsers..."
                playwright install --with-deps chromium 2>/dev/null || print_warning "Playwright browser install failed (non-critical)"
            fi
        fi
    fi

    return 0
}

setup_frontend() {
    print_info "Checking frontend..."

    if [ ! -d "frontend-react" ]; then
        print_error "frontend-react directory not found"
        return 1
    fi

    cd frontend-react

    # Only install if node_modules is missing
    if [ ! -d "node_modules" ]; then
        print_info "Installing frontend dependencies (first time setup)..."
        npm install
        print_success "Frontend packages installed"
    else
        print_success "Frontend packages ready"
    fi

    # Check for required UI utility files
    if [ ! -f "src/lib/utils.ts" ]; then
        print_warning "UI utility file missing, creating src/lib/utils.ts..."
        mkdir -p src/lib
        cat > src/lib/utils.ts << 'EOF'
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
EOF
        print_success "Created src/lib/utils.ts (required for UI components)"
    fi

    cd ..
    return 0
}

setup_databases() {
    print_info "Checking databases..."

    # Create data directory if it doesn't exist
    if [ ! -d "data" ]; then
        mkdir -p data
    fi

    # Check if databases exist
    local needs_init=false
    if [ ! -f "data/jps_aggregate.db" ] || [ ! -f "data/jps_users.db" ]; then
        needs_init=true
    fi

    if [ "$needs_init" = true ]; then
        print_info "Initializing databases (first time setup)..."

        # Run setup script
        if [ -f "scripts/setup_databases.py" ]; then
            $PYTHON_CMD scripts/setup_databases.py
            print_success "Databases initialized"
        else
            # Fallback: run migrations
            export FLASK_APP=run.py
            $PYTHON_CMD -m flask db upgrade
            print_success "Database migrations completed"
        fi
    else
        # Silently check and apply any pending migrations
        export FLASK_APP=run.py
        if ! $PYTHON_CMD -m flask db current 2>/dev/null | grep -q "head"; then
            print_info "Applying database migrations..."
            $PYTHON_CMD -m flask db upgrade 2>/dev/null
        fi
        print_success "Databases ready"
    fi

    return 0
}

configure_env() {
    local mode="${1:-development}"

    # Check if .env exists and has the right environment
    if [ -f ".env" ]; then
        local current_env=$(grep "^ENVIRONMENT=" .env 2>/dev/null | cut -d'=' -f2)
        if [ "$current_env" = "$mode" ]; then
            print_success "Using existing $mode configuration"
            return 0
        fi
    fi

    print_info "Creating $mode configuration..."

    # Preserve existing values if available
    local existing_secret=""
    local existing_domain=""
    local existing_cloudflare=""

    if [ -f ".env" ]; then
        existing_secret=$(grep "^SECRET_KEY=" .env 2>/dev/null | cut -d'=' -f2)
        existing_domain=$(grep "^PRODUCTION_DOMAIN=" .env 2>/dev/null | cut -d'=' -f2)
        existing_cloudflare=$(grep "^CLOUDFLARE_TUNNEL_TOKEN=" .env 2>/dev/null | cut -d'=' -f2)
    fi

    # Generate or preserve SECRET_KEY
    local secret_key="$existing_secret"
    if [ -z "$secret_key" ]; then
        secret_key=$($PYTHON_CMD -c "import secrets; print(secrets.token_hex(32))")
    fi

    # Base configuration for both environments
    cat > .env << EOF
# JPS Prospect Aggregate - $(echo $mode | tr '[:lower:]' '[:upper:]') Environment
# Generated by launcher on $(date)

ENVIRONMENT=$mode
SECRET_KEY=$secret_key
FLASK_APP=run.py

# Database paths are NOT set here - the app will use relative paths
# and convert them to absolute at runtime for portability
# DATABASE_URL=  # DO NOT SET - leave commented
# USER_DATABASE_URL=  # DO NOT SET - leave commented

EOF

    if [ "$mode" = "development" ]; then
        cat >> .env << EOF
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
EOF
    else
        # Production mode - handle domain
        local domain="$existing_domain"
        if [ -n "$existing_domain" ]; then
            print_info "Current domain: $existing_domain"
            if ! confirm "Keep existing domain?" "y"; then
                domain=$(prompt_user "Enter new production domain (e.g., app.example.com)" "")
                if [ -z "$domain" ]; then
                    print_error "Domain is required for production"
                    return 1
                fi
            fi
        else
            domain=$(prompt_user "Enter your production domain (e.g., app.example.com)" "")
            if [ -z "$domain" ]; then
                print_error "Domain is required for production"
                return 1
            fi
        fi

        # Cloudflare tunnel (optional)
        local cloudflare_token="$existing_cloudflare"
        if [ -n "$existing_cloudflare" ]; then
            print_info "Cloudflare tunnel is currently configured"
            if ! confirm "Keep existing Cloudflare token?" "y"; then
                if confirm "Remove Cloudflare tunnel?" "n"; then
                    cloudflare_token=""
                else
                    cloudflare_token=$(prompt_user "Enter new Cloudflare tunnel token" "")
                fi
            fi
        else
            if confirm "Configure Cloudflare tunnel?" "n"; then
                cloudflare_token=$(prompt_user "Enter Cloudflare tunnel token" "")
            fi
        fi

        cat >> .env << EOF
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
CLOUDFLARE_TUNNEL_TOKEN=$cloudflare_token

# Features
ENABLE_LLM_ENHANCEMENT=True
ENABLE_DUPLICATE_DETECTION=True
FILE_FRESHNESS_SECONDS=86400

# Performance
WORKERS=12
TIMEOUT=120
EOF
    fi

    print_success "$mode configuration created"
    return 0
}

check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 1
    fi
    return 0
}

# Display useful commands based on mode
show_useful_commands() {
    local mode="$1"
    local backend_port="${2:-5001}"
    local frontend_port="${3:-3000}"

    print_header "Useful Commands"

    if [ "$mode" = "development" ]; then
        echo "📋 Development Commands:"
        echo ""
        echo "  View Logs:"
        echo "    tail -f logs/app.log                    # Application logs"
        echo "    tail -f $LAUNCHER_STATE_DIR/backend.log # Backend server log"
        echo "    tail -f $LAUNCHER_STATE_DIR/frontend.log # Frontend server log"
        echo ""
        echo "  Server Control:"
        echo "    Ctrl+C                                  # Stop all servers"
        echo "    ./launch.sh --dev                       # Restart servers"
        echo "    lsof -ti:$backend_port | xargs kill -9              # Force kill backend"
        echo "    lsof -ti:$frontend_port | xargs kill -9              # Force kill frontend"
        echo ""
        echo "  Run Scrapers:"
        echo "    $PYTHON_CMD scripts/run_all_scrapers.py              # Run all scrapers"
        echo "    $PYTHON_CMD -m scripts.scrapers.run_scraper --source \"DHS\"  # Run specific scraper"
        echo ""
        echo "  Database Management:"
        echo "    $PYTHON_CMD scripts/setup_databases.py               # Reinitialize databases"
        echo "    sqlite3 data/jps_aggregate.db '.backup backups/backup.db'  # Backup database"
        echo "    $PYTHON_CMD -m flask db upgrade                      # Run migrations"
        echo ""
        echo "  Testing:"
        echo "    $PYTHON_CMD -m pytest tests/ -v                      # Run backend tests"
        echo "    cd frontend-react && npm test          # Run frontend tests"
        echo ""
        echo "  Health Check:"
        echo "    curl http://localhost:$backend_port/health           # Check API health"
        echo "    curl http://localhost:$frontend_port                 # Check frontend"
        echo ""
        echo "  Quick Actions:"
        echo "    ./launch.sh --quick                     # Quick restart"
        echo "    ./switch-env.sh prod                    # Switch to production"
        echo ""
    elif [ "$mode" = "production" ]; then
        local compose_cmd="docker-compose"
        if ! command_exists docker-compose; then
            compose_cmd="docker compose"
        fi

        echo "📋 Your containers are running in the background. Use these commands to manage them:"
        echo ""
        echo "  View Status & Logs:"
        echo "    $compose_cmd ps                        # Check container status"
        echo "    $compose_cmd logs -f web               # Follow application logs (Ctrl+C to exit)"
        echo "    $compose_cmd logs -f ollama            # Follow Ollama logs"
        echo "    $compose_cmd logs --tail=100 web       # View last 100 log lines"
        echo ""
        echo "  Stop & Restart Services:"
        echo "    ./launch.sh --stop                     # Stop all services properly"

        # Check if Cloudflare is enabled and show appropriate manual command
        if grep -q "CLOUDFLARE_TUNNEL_TOKEN=." .env 2>/dev/null; then
            echo "    $compose_cmd --profile cloudflare down # Manual stop (includes Cloudflare)"
        else
            echo "    $compose_cmd down                      # Manual stop command"
        fi

        echo "    $compose_cmd stop                      # Stop containers (keep data)"
        echo "    $compose_cmd restart                   # Restart all services"
        echo "    $compose_cmd restart web               # Restart web service only"
        echo "    $compose_cmd up -d                     # Start containers again"
        echo ""
        echo "  Database Management:"
        echo "    docker exec jps-web sqlite3 /app/data/jps_aggregate.db '.backup /app/backups/backup_\$(date +%Y%m%d).db'"
        echo "                                            # Backup database"
        echo "    docker exec jps-web python -m flask db upgrade  # Run migrations"
        echo "    docker exec -it jps-web sqlite3 /app/data/jps_aggregate.db  # Access database shell"
        echo ""
        echo "  Run Scrapers:"
        echo "    docker exec jps-web python scripts/run_all_scrapers.py  # Run all scrapers"
        echo "    docker exec jps-web python -m scripts.scrapers.run_scraper --source \"DHS\"  # Run specific scraper"
        echo ""
        echo "  Container Access:"
        echo "    docker exec -it jps-web /bin/bash      # Open shell in container"
        echo "    docker exec jps-web ls -la /app/data   # List data files"
        echo ""
        echo "  Health Monitoring:"
        echo "    curl http://localhost:5001/health      # Check if app is healthy"
        echo "    docker stats                           # Monitor resource usage (Ctrl+C to exit)"
        echo "    $compose_cmd top                       # View running processes"
        echo ""
        echo "  Quick Actions:"
        echo "    ./launch.sh                            # Run launcher again"
        echo "    ./deploy-production-v2.sh               # Redeploy application"
        echo "    ./switch-env.sh dev                     # Switch to development mode"
        echo ""

        # Add Cloudflare-specific commands if configured
        if grep -q "CLOUDFLARE_TUNNEL_TOKEN=." .env 2>/dev/null; then
            echo "  Cloudflare Tunnel:"
            echo "    $compose_cmd logs -f cloudflared       # Follow tunnel logs"
            echo "    $compose_cmd restart cloudflared       # Restart tunnel service"
            echo ""
        fi
    fi

    echo "💡 Tips:"
    echo "  • Use './launch.sh --help' for more options"
    echo "  • Check './launch.sh' maintenance menu (option 4) for more tools"
    echo "  • Logs are stored in: logs/ and $LAUNCHER_STATE_DIR/"
    echo ""
}

start_dev_servers() {
    print_header "Starting Development Servers"

    # Check if ports are available
    local backend_port=5001
    local frontend_port=3000

    if ! check_port $backend_port; then
        print_warning "Port $backend_port is already in use"
        if confirm "Kill existing process on port $backend_port?"; then
            lsof -ti:$backend_port | xargs kill -9 2>/dev/null || true
            sleep 1
            print_success "Port $backend_port cleared"
        else
            backend_port=$(prompt_user "Enter alternative backend port" "5002")
            # Update .env with new port
            sed -i.bak "s/PORT=.*/PORT=$backend_port/" .env
        fi
    fi

    if ! check_port $frontend_port; then
        print_warning "Port $frontend_port is already in use"
        if confirm "Kill existing process on port $frontend_port?"; then
            lsof -ti:$frontend_port | xargs kill -9 2>/dev/null || true
            sleep 1
            print_success "Port $frontend_port cleared"
        else
            print_error "Cannot start frontend with port $frontend_port in use"
            return 1
        fi
    fi

    # Start backend
    print_info "Starting backend server on port $backend_port..."
    $PYTHON_CMD run.py > "$LAUNCHER_STATE_DIR/backend.log" 2>&1 &
    local backend_pid=$!
    echo $backend_pid > "$LAUNCHER_STATE_DIR/backend.pid"

    # Wait for backend to start
    local count=0
    while ! curl -s http://localhost:$backend_port/health >/dev/null 2>&1; do
        sleep 1
        count=$((count + 1))
        if [ $count -gt 30 ]; then
            print_error "Backend failed to start"
            cat "$LAUNCHER_STATE_DIR/backend.log" | tail -20
            return 1
        fi
    done
    print_success "Backend server started (PID: $backend_pid)"

    # Start frontend
    print_info "Starting frontend server on port $frontend_port..."
    cd frontend-react
    npm run dev > "$LAUNCHER_STATE_DIR/frontend.log" 2>&1 &
    local frontend_pid=$!
    echo $frontend_pid > "$LAUNCHER_STATE_DIR/frontend.pid"
    cd ..

    # Wait for frontend to start
    sleep 3
    print_success "Frontend server started (PID: $frontend_pid)"

    # Open browser
    local open_cmd=$(get_open_command)
    if [ -n "$open_cmd" ]; then
        print_info "Opening browser..."
        $open_cmd "http://localhost:$frontend_port" 2>/dev/null || true
    fi

    print_success "Development servers are running!"
    print_info "Backend: http://localhost:$backend_port"
    print_info "Frontend: http://localhost:$frontend_port"

    # Show useful commands
    show_useful_commands "development" "$backend_port" "$frontend_port"

    print_info "Press Ctrl+C to stop servers"

    # Save state
    save_preference "last_mode" "development"
    save_preference "backend_port" "$backend_port"
    save_preference "frontend_port" "$frontend_port"

    # Wait for interrupt
    trap 'stop_dev_servers; exit 0' INT TERM
    wait $backend_pid $frontend_pid
}

stop_dev_servers() {
    print_info "Stopping servers..."

    if [ -f "$LAUNCHER_STATE_DIR/backend.pid" ]; then
        kill $(cat "$LAUNCHER_STATE_DIR/backend.pid") 2>/dev/null || true
        rm "$LAUNCHER_STATE_DIR/backend.pid"
    fi

    if [ -f "$LAUNCHER_STATE_DIR/frontend.pid" ]; then
        kill $(cat "$LAUNCHER_STATE_DIR/frontend.pid") 2>/dev/null || true
        rm "$LAUNCHER_STATE_DIR/frontend.pid"
    fi

    print_success "Servers stopped"
}

setup_development() {
    print_header "Starting Development Mode"

    # Quick setup - only do what's necessary
    configure_env "development" || return 1   # Create .env if missing
    setup_python_env || return 1              # Activate/create venv
    install_python_deps || return 1           # Install only if missing
    setup_frontend || return 1                # Install only if node_modules missing
    setup_databases || return 1               # Create only if missing, auto-migrate
    start_dev_servers || return 1             # Start the servers

    return 0
}

# ============================================================
# PRODUCTION MODE SETUP
# ============================================================

# configure_production is now handled by configure_env "production"

build_docker_images() {
    print_info "Building Docker images..."

    if ! check_docker; then
        print_error "Docker is required for production mode"
        return 1
    fi

    # Use docker-compose or docker compose depending on what's available
    local compose_cmd="docker-compose"
    if ! command_exists docker-compose; then
        compose_cmd="docker compose"
    fi

    print_info "Building images (this may take a few minutes)..."
    $compose_cmd build || {
        print_error "Docker build failed"
        return 1
    }

    print_success "Docker images built successfully"
    return 0
}

start_docker_services() {
    print_info "Starting Docker services..."

    local compose_cmd="docker-compose"
    if ! command_exists docker-compose; then
        compose_cmd="docker compose"
    fi

    # Stop existing containers (including all profiles)
    print_info "Stopping existing containers..."
    # Always use cloudflare profile when stopping to ensure all containers are removed
    $compose_cmd --profile cloudflare down 2>/dev/null || true

    # Check for Cloudflare tunnel
    local cloudflare_enabled=false
    if grep -q "CLOUDFLARE_TUNNEL_TOKEN=." .env 2>/dev/null; then
        cloudflare_enabled=true
    fi

    # Start services
    if [ "$cloudflare_enabled" = true ]; then
        print_info "Starting services with Cloudflare tunnel..."
        $compose_cmd --profile cloudflare up -d
    else
        print_info "Starting services..."
        $compose_cmd up -d
    fi

    print_success "Docker services started"
    return 0
}

stop_docker_services() {
    print_info "Stopping Docker services..."

    local compose_cmd="docker-compose"
    if ! command_exists docker-compose; then
        compose_cmd="docker compose"
    fi

    # Check for Cloudflare tunnel to use correct profile
    local cloudflare_enabled=false
    if grep -q "CLOUDFLARE_TUNNEL_TOKEN=." .env 2>/dev/null; then
        cloudflare_enabled=true
    fi

    # Stop services with appropriate profile
    if [ "$cloudflare_enabled" = true ]; then
        print_info "Stopping services with Cloudflare tunnel..."
        $compose_cmd --profile cloudflare down
    else
        print_info "Stopping services..."
        $compose_cmd down
    fi

    # Verify all containers are stopped
    if docker ps | grep -q "jps-"; then
        print_warning "Some containers may still be running. Forcing cleanup..."
        docker ps | grep "jps-" | awk '{print $1}' | xargs -r docker stop 2>/dev/null || true
    fi

    print_success "Docker services stopped"
    return 0
}

verify_deployment() {
    print_info "Verifying deployment..."

    # Wait for services to be ready
    print_info "Waiting for services to start..."
    sleep 10

    # Check health endpoint
    if curl -f http://localhost:5001/health >/dev/null 2>&1; then
        print_success "Application is healthy!"
    else
        print_warning "Health check failed - checking logs..."
        docker-compose logs --tail=50 web
        return 1
    fi

    # Display status
    print_header "Deployment Status"
    docker-compose ps

    # Get domain from .env
    local domain=$(grep "PRODUCTION_DOMAIN=" .env | cut -d'=' -f2)

    print_header "Access Information"
    print_success "Production deployment complete!"

    if grep -q "CLOUDFLARE_TUNNEL_TOKEN=." .env 2>/dev/null; then
        print_info "Application URL: https://$domain"
        print_info "Cloudflare tunnel is active"
    else
        print_info "Application URL: http://localhost:5001"
        print_info "Configure your reverse proxy to point to port 5001"
        print_info "Domain configured: $domain"
    fi

    # Show useful commands
    show_useful_commands "production"

    print_info "The application is running in Docker containers (background mode)"
    print_info "Use the commands above to manage your deployment"

    # Save state
    save_preference "last_mode" "production"

    return 0
}

setup_production() {
    print_header "Production Mode Setup"

    configure_env "production" || return 1
    build_docker_images || return 1
    start_docker_services || return 1
    verify_deployment || return 1

    return 0
}

# ============================================================
# QUICK START MODE
# ============================================================

quick_start() {
    print_header "Quick Start"

    print_info "Auto-detecting best configuration..."

    # Check what's available
    local has_docker=false
    if check_docker 2>/dev/null; then
        has_docker=true
    fi

    # Check current environment
    local current_env=$(detect_current_environment)
    local last_mode=$(get_preference "last_mode" "")

    # Decide what to do
    if [ -n "$last_mode" ]; then
        print_info "Last used mode: $last_mode"
        if confirm "Use $last_mode mode?"; then
            if [ "$last_mode" = "production" ]; then
                setup_production
            else
                setup_development
            fi
        else
            main_menu
        fi
    elif [ "$current_env" = "production" ] && [ "$has_docker" = true ]; then
        print_info "Production environment detected"
        setup_production
    elif [ "$current_env" = "development" ]; then
        print_info "Development environment detected"
        setup_development
    elif [ "$has_docker" = true ]; then
        print_info "Docker available - recommending production mode"
        if confirm "Setup production mode?"; then
            setup_production
        else
            setup_development
        fi
    else
        print_info "Starting development mode"
        setup_development
    fi
}

# ============================================================
# MAINTENANCE MENU
# ============================================================

maintenance_menu() {
    while true; do
        print_header "Maintenance & Tools"
        echo "  [1] Database backup"
        echo "  [2] Database restore"
        echo "  [3] Run all scrapers"
        echo "  [4] Run specific scraper"
        echo "  [5] Clean old data files"
        echo "  [6] Check system health"
        echo "  [7] View logs"
        echo "  [8] Reset & Reinstall Options"
        echo "  [9] Update dependencies"
        echo "  [10] Run tests"
        echo "  [0] Back to main menu"
        echo ""

        local choice=$(prompt_user "Select option" "")

        case $choice in
            1)
                backup_database
                ;;
            2)
                restore_database
                ;;
            3)
                run_all_scrapers
                ;;
            4)
                run_specific_scraper
                ;;
            5)
                clean_data_files
                ;;
            6)
                check_system_health
                ;;
            7)
                view_logs_menu
                ;;
            8)
                reset_environment
                ;;
            9)
                update_dependencies
                ;;
            10)
                run_tests
                ;;
            0)
                return 0
                ;;
            *)
                print_error "Invalid option"
                ;;
        esac

        echo ""
        read -p "Press Enter to continue..."
    done
}

backup_database() {
    print_header "Database Backup"

    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_dir="$PROJECT_ROOT/backups"

    mkdir -p "$backup_dir"

    if [ -f "data/jps_aggregate.db" ]; then
        local backup_file="$backup_dir/jps_aggregate_$timestamp.db"
        cp "data/jps_aggregate.db" "$backup_file"
        print_success "Main database backed up to: $backup_file"
    fi

    if [ -f "data/jps_users.db" ]; then
        local backup_file="$backup_dir/jps_users_$timestamp.db"
        cp "data/jps_users.db" "$backup_file"
        print_success "User database backed up to: $backup_file"
    fi
}

restore_database() {
    print_header "Database Restore"

    local backup_dir="$PROJECT_ROOT/backups"

    if [ ! -d "$backup_dir" ]; then
        print_error "No backups found"
        return 1
    fi

    print_info "Available backups:"
    ls -la "$backup_dir"/*.db 2>/dev/null || {
        print_error "No backup files found"
        return 1
    }

    local backup_file=$(prompt_user "Enter backup filename to restore" "")

    if [ -f "$backup_dir/$backup_file" ]; then
        if confirm "Restore from $backup_file? This will overwrite current database!"; then
            # Determine which database to restore
            if [[ "$backup_file" == *"jps_aggregate"* ]]; then
                cp "$backup_dir/$backup_file" "data/jps_aggregate.db"
                print_success "Main database restored"
            elif [[ "$backup_file" == *"jps_users"* ]]; then
                cp "$backup_dir/$backup_file" "data/jps_users.db"
                print_success "User database restored"
            fi
        fi
    else
        print_error "Backup file not found"
    fi
}

run_all_scrapers() {
    print_header "Run All Scrapers"

    if [ -f "scripts/run_all_scrapers.py" ]; then
        print_info "Starting all scrapers..."
        $PYTHON_CMD scripts/run_all_scrapers.py
    else
        print_error "Scraper script not found"
    fi
}

run_specific_scraper() {
    print_header "Run Specific Scraper"

    print_info "Available scrapers:"
    echo "  1. DHS - Department of Homeland Security"
    echo "  2. DOC - Department of Commerce"
    echo "  3. DOJ - Department of Justice"
    echo "  4. DOS - Department of State"
    echo "  5. DOT - Department of Transportation"
    echo "  6. HHS - Health and Human Services"
    echo "  7. SSA - Social Security Administration"
    echo "  8. TREAS - Department of Treasury"
    echo "  9. ACQGW - Acquisition Gateway"

    local choice=$(prompt_user "Select scraper" "")

    local scrapers=("DHS" "DOC" "DOJ" "DOS" "DOT" "HHS" "SSA" "TREAS" "ACQGW")

    if [ "$choice" -ge 1 ] && [ "$choice" -le 9 ]; then
        local scraper=${scrapers[$((choice-1))]}
        print_info "Running $scraper scraper..."
        $PYTHON_CMD -m scripts.scrapers.run_scraper --source "$scraper"
    else
        print_error "Invalid selection"
    fi
}

clean_data_files() {
    print_header "Clean Old Data Files"

    if [ -f "app/utils/data_retention.py" ]; then
        print_info "Analyzing data files..."
        $PYTHON_CMD app/utils/data_retention.py

        if confirm "Execute cleanup?"; then
            $PYTHON_CMD app/utils/data_retention.py --execute
            print_success "Data files cleaned"
        fi
    else
        print_error "Data retention script not found"
    fi
}

check_system_health() {
    print_header "System Health Check"

    # Check disk space
    print_info "Disk usage:"
    df -h "$PROJECT_ROOT" | tail -1

    # Check database sizes
    if [ -f "data/jps_aggregate.db" ]; then
        local size=$(du -h "data/jps_aggregate.db" | cut -f1)
        print_info "Main database size: $size"
    fi

    # Check if services are running
    if [ -f "$LAUNCHER_STATE_DIR/backend.pid" ]; then
        if kill -0 $(cat "$LAUNCHER_STATE_DIR/backend.pid") 2>/dev/null; then
            print_success "Backend is running"
        else
            print_warning "Backend PID exists but process not running"
        fi
    fi

    # Check API health
    if curl -f http://localhost:5001/health >/dev/null 2>&1; then
        print_success "API is healthy"
    else
        print_warning "API health check failed"
    fi

    # Check Docker if in production
    if [ "$(detect_current_environment)" = "production" ]; then
        if command_exists docker; then
            print_info "Docker containers:"
            docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        fi
    fi
}

view_logs_menu() {
    print_header "View Logs"

    echo "  [1] Application logs"
    echo "  [2] Launcher logs"
    echo "  [3] Backend logs (development)"
    echo "  [4] Frontend logs (development)"
    echo "  [5] Docker logs (production)"

    local choice=$(prompt_user "Select log to view" "")

    case $choice in
        1)
            if [ -f "logs/app.log" ]; then
                tail -f logs/app.log
            else
                print_error "Application log not found"
            fi
            ;;
        2)
            if [ -f "$LOG_FILE" ]; then
                tail -f "$LOG_FILE"
            else
                print_error "Launcher log not found"
            fi
            ;;
        3)
            if [ -f "$LAUNCHER_STATE_DIR/backend.log" ]; then
                tail -f "$LAUNCHER_STATE_DIR/backend.log"
            else
                print_error "Backend log not found"
            fi
            ;;
        4)
            if [ -f "$LAUNCHER_STATE_DIR/frontend.log" ]; then
                tail -f "$LAUNCHER_STATE_DIR/frontend.log"
            else
                print_error "Frontend log not found"
            fi
            ;;
        5)
            if command_exists docker-compose; then
                docker-compose logs -f
            elif command_exists docker; then
                docker compose logs -f
            else
                print_error "Docker not available"
            fi
            ;;
        *)
            print_error "Invalid selection"
            ;;
    esac
}

reset_environment() {
    print_header "Reset & Reinstall Options"

    echo "Choose what to reset:"
    echo "  [1] Reset configuration (.env file)"
    echo "  [2] Reinstall Python packages"
    echo "  [3] Reinstall frontend packages"
    echo "  [4] Reinitialize databases"
    echo "  [5] Full reset (all of the above)"
    echo "  [6] Clear caches and temporary files"
    echo "  [0] Cancel"
    echo ""

    local choice=$(prompt_user "Select option" "0")

    case $choice in
        1)
            print_info "Resetting configuration..."
            if [ -f ".env" ]; then
                cp .env ".env.backup-$(date +%Y%m%d_%H%M%S)"
                print_info "Current .env backed up"
                rm -f .env
            fi
            print_success "Configuration reset - will be recreated on next run"
            ;;
        2)
            print_info "Reinstalling Python packages..."
            $PYTHON_CMD -m pip install --force-reinstall -r requirements.txt
            print_success "Python packages reinstalled"
            ;;
        3)
            print_info "Reinstalling frontend packages..."
            cd frontend-react
            rm -rf node_modules package-lock.json
            npm install
            cd ..
            print_success "Frontend packages reinstalled"
            ;;
        4)
            if confirm "This will DELETE all data. Are you sure?" "n"; then
                print_info "Reinitializing databases..."
                rm -f data/jps_aggregate.db data/jps_users.db
                if [ -f "scripts/setup_databases.py" ]; then
                    $PYTHON_CMD scripts/setup_databases.py
                else
                    export FLASK_APP=run.py
                    $PYTHON_CMD -m flask db upgrade
                fi
                print_success "Databases reinitialized"
            fi
            ;;
        5)
            if confirm "This will reset EVERYTHING. Are you sure?" "n"; then
                print_warning "Performing full reset..."

                # Backup .env
                if [ -f ".env" ]; then
                    cp .env ".env.backup-$(date +%Y%m%d_%H%M%S)"
                fi

                # Reset everything
                rm -f .env
                rm -f data/jps_aggregate.db data/jps_users.db
                rm -rf frontend-react/node_modules
                rm -rf "$LAUNCHER_STATE_DIR"

                print_success "Full reset complete"
                print_info "Run './launch.sh' to set up fresh"
            fi
            ;;
        6)
            print_info "Clearing caches..."
            rm -rf __pycache__ .pytest_cache
            find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
            rm -rf logs/*.log
            rm -rf "$LAUNCHER_STATE_DIR"/*.log
            print_success "Caches cleared"
            ;;
        0)
            print_info "Reset cancelled"
            ;;
        *)
            print_error "Invalid option"
            ;;
    esac
}

update_dependencies() {
    print_header "Update Dependencies"

    if confirm "Update Python packages?"; then
        print_info "Updating Python packages..."
        $PYTHON_CMD -m pip install --upgrade -r requirements.txt
        print_success "Python packages updated"
    fi

    if confirm "Update npm packages?"; then
        print_info "Updating frontend packages..."
        cd frontend-react
        npm update
        cd ..
        print_success "Frontend packages updated"
    fi

    if command_exists docker && confirm "Update Docker images?" "n"; then
        print_info "Pulling latest Docker images..."
        docker pull ollama/ollama:latest
        print_success "Docker images updated"
    fi
}

run_tests() {
    print_header "Run Tests"

    echo "  [1] Backend tests"
    echo "  [2] Frontend tests"
    echo "  [3] All tests"

    local choice=$(prompt_user "Select tests to run" "3")

    case $choice in
        1|3)
            print_info "Running backend tests..."
            $PYTHON_CMD -m pytest tests/ -v
            ;;
    esac

    case $choice in
        2|3)
            print_info "Running frontend tests..."
            cd frontend-react
            npm test
            cd ..
            ;;
    esac
}

# ============================================================
# MAIN MENU
# ============================================================

show_banner() {
    clear
    print_color "$CYAN" "
     ██╗██████╗ ███████╗    ██╗      █████╗ ██╗   ██╗███╗   ██╗ ██████╗██╗  ██╗███████╗██████╗
     ██║██╔══██╗██╔════╝    ██║     ██╔══██╗██║   ██║████╗  ██║██╔════╝██║  ██║██╔════╝██╔══██╗
     ██║██████╔╝███████╗    ██║     ███████║██║   ██║██╔██╗ ██║██║     ███████║█████╗  ██████╔╝
██   ██║██╔═══╝ ╚════██║    ██║     ██╔══██║██║   ██║██║╚██╗██║██║     ██╔══██║██╔══╝  ██╔══██╗
╚█████╔╝██║     ███████║    ███████╗██║  ██║╚██████╔╝██║ ╚████║╚██████╗██║  ██║███████╗██║  ██║
 ╚════╝ ╚═╝     ╚══════╝    ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
"
    print_color "$WHITE" "                    JPS Prospect Aggregate - Unified Launcher v$SCRIPT_VERSION"
    print_color "$WHITE" "                           Simplifying Your Development Workflow"
    echo ""
}

main_menu() {
    while true; do
        show_banner

        # Show current status
        local current_env=$(detect_current_environment)
        if [ "$current_env" != "none" ]; then
            print_info "Current environment: $current_env"
        fi

        print_header "Main Menu"
        echo "  $ROCKET [1] Development Mode (Local)"
        echo "  $GLOBE [2] Production Mode (Docker)"
        echo "  ⚡ [3] Quick Start (Auto-detect)"
        echo "  $GEAR [4] Maintenance & Tools"
        echo "  ❌ [5] Exit"
        echo ""

        local choice=$(prompt_user "Select option" "3")

        case $choice in
            1)
                setup_development
                break
                ;;
            2)
                setup_production
                break
                ;;
            3)
                quick_start
                break
                ;;
            4)
                maintenance_menu
                ;;
            5)
                print_info "Goodbye!"
                exit 0
                ;;
            *)
                print_error "Invalid option"
                sleep 1
                ;;
        esac
    done
}

# ============================================================
# MAIN EXECUTION
# ============================================================

main() {
    # Initialize
    init_launcher_state
    detect_os

    # Parse command line arguments
    case "${1:-}" in
        --help|-h)
            print_header "JPS Launcher Help"
            echo "Usage: ./launch.sh [option]"
            echo ""
            echo "Options:"
            echo "  --help, -h                  Show this help message"
            echo "  --version, -v               Show version information"
            echo "  --dev                       Start development mode directly"
            echo "  --prod                      Start production mode directly"
            echo "  --stop                      Stop Docker production services"
            echo "  --quick                     Quick start with auto-detection"
            echo "  --check                     Check prerequisites only"
            echo ""
            echo "Without options, the interactive menu will be shown."
            exit 0
            ;;
        --version|-v)
            echo "JPS Launcher version $SCRIPT_VERSION"
            exit 0
            ;;
        --dev)
            check_prerequisites || exit 1
            setup_development
            exit $?
            ;;
        --prod)
            check_prerequisites || exit 1
            setup_production
            exit $?
            ;;
        --stop)
            if ! check_docker 2>/dev/null; then
                print_error "Docker is not running or not installed"
                exit 1
            fi
            stop_docker_services
            exit $?
            ;;
        --quick)
            check_prerequisites || exit 1
            quick_start
            exit $?
            ;;
        --check)
            check_prerequisites
            exit $?
            ;;
        *)
            # Interactive mode
            check_prerequisites || {
                print_error "Prerequisites check failed"
                print_info "Please install missing dependencies and try again"
                exit 1
            }
            main_menu
            ;;
    esac
}

# Run main function
main "$@"
