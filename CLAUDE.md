# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Quick Start

```bash
# Using the unified launcher (RECOMMENDED)
./launch.sh --dev                              # Start development environment
./launch.sh --prod                             # Start production (Docker)
./launch.sh                                    # Interactive menu with options

# Manual commands
python run.py                                 # Backend (port 5001)
cd frontend-react && npm run dev              # Frontend (port 3000)

# Run scrapers
python -m scripts.scrapers.run_scraper --source "DHS"  # Specific scraper
python scripts/scrapers/run_all_scrapers.py            # All scrapers

# Database
python scripts/setup/setup_databases.py       # Initialize
cd migrations && alembic upgrade head         # Migrations

# Testing
python -m pytest                              # Backend tests
cd frontend-react && npm test                 # Frontend tests
make test-ci                                  # Full CI suite locally

# LLM Enhancement
python scripts/enrichment/enhance_prospects_with_llm.py values --limit 100

# The environment is automatically configured based on the mode:
# --dev sets ENVIRONMENT=development
# --prod sets ENVIRONMENT=production
```

## Setup

### Prerequisites
- Python 3.11+ (required)
- Node.js 20.x (frontend)
- Ollama with qwen3:latest model (LLM features)
- Playwright browsers: `playwright install`

### Local Development
```bash
# 1. Python environment
conda activate your_env

# 2. Install dependencies
pip install -r requirements.txt
playwright install

# 3. Configure environment
cp .env.example .env
# Edit .env: Set ENVIRONMENT=development

# 4. Initialize database
python scripts/setup/setup_databases.py

# 5. Frontend setup
cd frontend-react && npm install
```

### Docker Production
```bash
# Use the launcher for production
./launch.sh --prod

# Or manually:
cp .env.example .env
# Edit .env: Set ENVIRONMENT=production and other settings
docker-compose up --build -d
```

## Essential Commands

### Development
```bash
python run.py                                  # Start backend
cd frontend-react && npm run dev               # Start frontend
python -m scripts.scrapers.run_scraper --source "DHS"   # Run scraper
python scripts/scrapers/test_scraper_individual.py --scraper dhs  # Test scraper
```

### Production Deployment
```bash
# Deploy with launcher
./launch.sh --prod                              # Handles everything

# Docker management (after deployment)
docker-compose up -d                            # Start
./launch.sh --stop                              # Stop all services
docker-compose restart                          # Restart
docker-compose logs -f web                      # Logs

# With Cloudflare tunnel
docker-compose --profile cloudflare up -d

# Database backup
docker exec jps-web sqlite3 /app/data/jps_aggregate.db '.backup /app/backups/backup.db'
```

### Database & Migrations

#### IMPORTANT: Migration Management
To prevent database schema mismatches, **ALWAYS** follow this workflow when changing models:

```bash
# 1. After changing any model (models.py):
flask db migrate -m "Description of changes"   # Generate migration

# 2. Review the generated migration file in migrations/versions/
# 3. Apply the migration:
flask db upgrade                               # Apply migration

# 4. If there are issues:
flask db downgrade                             # Rollback last migration
flask db history                               # View migration history
flask db current                               # Check current version
```

#### Common Database Commands
```bash
python scripts/setup/setup_databases.py        # Initial setup
sqlite3 data/jps_aggregate.db "VACUUM;"        # Optimize database
flask db stamp head                            # Mark DB as up-to-date (use carefully!)
```

#### Troubleshooting Schema Mismatches
If you encounter "no such column" errors:
1. Check current migration: `flask db current`
2. Check pending migrations: `flask db heads`
3. Apply migrations: `flask db upgrade`
4. If still broken: `flask db stamp head` (last resort)

### Testing
```bash
python -m pytest tests/ -v                     # All tests
python -m pytest tests/api/ -v                 # API tests
cd frontend-react && npm test                  # Frontend tests
make test-ci                                   # Local CI testing
```

### Maintenance
```bash
./scripts/database/backup.sh                   # Backup DB
python app/utils/data_retention.py --execute   # Clean old files
python scripts/scrapers/monitor_scrapers.py    # Monitor status
python scripts/data_processing/export_decisions_for_llm.py  # Export decisions
```

## Architecture Overview

### Scraper System
- **Base Class**: `ConsolidatedScraperBase` - Unified scraping framework
- **Config**: `ScraperConfig` dataclass defines behavior
- **Scrapers**: 9 agencies (ACQGW, SSA, DOC, HHS, DHS, DOJ, DOS, TREAS, DOT)

### Database
- **Models**: SQLAlchemy with SQLite
- **Migrations**: Alembic-managed
- **Dual DB**: Main prospects + separate user auth

### API Endpoints
```
/api/prospects/           # CRUD operations
/api/decisions/           # Go/no-go decisions
/api/llm/enhance          # AI enhancement
/api/admin/               # Admin functions
/api/scrapers/run         # Trigger scrapers
```

### Frontend
- React + TypeScript
- TanStack Table (virtualization)
- TanStack Query (state management)
- Tailwind CSS + Radix UI
- **Note**: UI components require `src/lib/utils.ts` for the `cn` utility function (auto-created by launch.sh if missing)

## Creating a New Scraper

1. Add configuration in `app/core/scraper_configs.py`:
```python
YOUR_AGENCY_CONFIG = ScraperConfig(
    source_name="Your Agency",
    folder_name="your_agency",
    base_url="https://agency.gov",
    # Additional config...
)
```

2. Create scraper in `app/core/scrapers/your_agency.py`:
```python
from app.core.consolidated_scraper_base import ConsolidatedScraperBase
from app.core.scraper_configs import YOUR_AGENCY_CONFIG


class YourAgencyScraper(ConsolidatedScraperBase):
    def __init__(self):
        super().__init__(YOUR_AGENCY_CONFIG)
```

3. Register in `app/core/scrapers/__init__.py`
4. Test: `python scripts/scrapers/test_scraper_individual.py --scraper your_agency`

## Environment Variables

### Required
```bash
SECRET_KEY=<generate-with-command-below>
ENVIRONMENT=development  # or production
```

Generate SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Production-Specific
```bash
# Core production setting - other URLs auto-configured from this
PRODUCTION_DOMAIN=app.example.com  # Your domain (without https://)

# Optional - for Cloudflare tunnel
CLOUDFLARE_TUNNEL_TOKEN=<your-tunnel-token>

# Auto-configured from PRODUCTION_DOMAIN:
# ALLOWED_ORIGINS=https://${PRODUCTION_DOMAIN},http://localhost:3000,http://localhost:5001
# VITE_API_URL=https://${PRODUCTION_DOMAIN}
```

### Database
```bash
DATABASE_URL=sqlite:///data/jps_aggregate.db
USER_DATABASE_URL=sqlite:///data/jps_users.db
```

### LLM
```bash
OLLAMA_BASE_URL=http://localhost:11434  # Local
OLLAMA_BASE_URL=http://ollama:11434     # Docker
OLLAMA_MODEL=qwen3:latest
```

## Common Issues

### Port Conflicts
```bash
lsof -i :5001 && kill -9 <PID>           # Backend port
lsof -i :11434 && kill -9 <PID>          # Ollama port
```

### Database Issues
```bash
rm data/*.db && python scripts/setup/setup_databases.py  # Reset DB
sqlite3 data/jps_aggregate.db "PRAGMA journal_mode=WAL;"  # Fix locks
```

### Scraper Issues
```bash
playwright install --with-deps            # Browser issues
# Stuck scrapers: Check logs/error_screenshots/
```

### Frontend Issues
```bash
cd frontend-react
rm -rf node_modules && npm install       # Clean reinstall
```

### Ollama Issues
```bash
ollama pull qwen3:latest                  # Download model
ollama serve                              # Start service
```

## Project Structure

```
/
├── app/                   # Backend application
│   ├── api/              # API endpoints
│   ├── core/             # Scraper framework
│   │   ├── consolidated_scraper_base.py
│   │   ├── scraper_configs.py
│   │   └── scrapers/     # Agency scrapers
│   ├── database/         # Models & operations
│   ├── services/         # Business logic
│   └── utils/            # Utilities
├── frontend-react/        # React frontend
├── tests/                 # Backend tests
├── scripts/               # Utility scripts
├── migrations/            # Alembic migrations
├── ci-test/              # Local CI testing
├── docker/               # Docker configs
├── data/                 # SQLite databases
│   ├── raw/             # Scraped files
│   └── processed/       # Exports
└── logs/                 # Application logs
```

## Testing & CI/CD

### Quick Testing
```bash
make test-ci              # Full CI suite locally
make test-python          # Python only
make test-frontend        # Frontend only
```

### Coverage Requirements
- Backend: 75% minimum
- Frontend: 80% minimum

### Pre-commit Hooks
```bash
pre-commit install        # Setup
pre-commit run --all-files  # Run manually
```

### CI Pipeline Stages
1. Parallel Python/Frontend testing
2. Integration tests
3. E2E tests (Playwright)
4. Security scanning

## Key Workflows

### Feature Development
```bash
git checkout -b feature/name
# Make changes
python -m pytest tests/ -v
pre-commit run --all-files
git commit -m "feat: description"
```

### Database Migration
```bash
cd migrations
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Debugging
- Screenshots: `logs/error_screenshots/`
- HTML dumps: `logs/error_html/`
- Logs: `logs/app.log`, `logs/scrapers.log`

## User Management

```bash
python scripts/operations/manage_users.py  # User management utilities
```

Roles:
- **user**: Basic access
- **admin**: Manage scrapers
- **super-admin**: Full system access

## Production Deployment Guide

### Overview
The project includes automated scripts for simplified production deployment with Docker and optional Cloudflare tunnel integration.

### Quick Deployment
```bash
# Deploy to production
./launch.sh --prod
```

### What the launcher does in production mode:
1. Generates cryptographically secure SECRET_KEY (first time only)
2. Prompts for your production domain (or keeps existing)
3. Optionally configures Cloudflare tunnel (or keeps existing)
4. Creates/updates `.env` with production settings
5. Sets up required directories (data, logs, backups)
6. Builds Docker images
7. Starts services (web, ollama, optional cloudflare)
8. Runs health checks
9. Displays management commands

**Smart prompting**: The launcher preserves your domain and Cloudflare settings between runs, only asking if you want to change them.

### Key Configuration Pattern
The production setup uses a simplified configuration where you only need to set `PRODUCTION_DOMAIN`:
```bash
# Set this in .env (launcher does this for you)
PRODUCTION_DOMAIN=app.example.com

# These are auto-configured:
ALLOWED_ORIGINS=https://app.example.com,http://localhost:3000,http://localhost:5001
VITE_API_URL=https://app.example.com
```

### Docker Services
- **web**: Flask app with Waitress (12 workers), auto-restarts
- **ollama**: LLM service, auto-downloads qwen3:latest on first run
- **cloudflared**: Optional Cloudflare tunnel (profile-based activation)

### Data Persistence
All critical data persists through Docker volumes:
- `./data`: SQLite databases (main + user auth)
- `./logs`: Application and scraper logs
- `./backups`: Database backups

### Production Commands
```bash
# View real-time logs
docker-compose logs -f web

# Stop everything
docker-compose down

# Restart services
docker-compose restart web

# Backup database
docker exec jps-web sqlite3 /app/data/jps_aggregate.db '.backup /app/backups/backup_$(date +%Y%m%d).db'

# Check health
curl http://localhost:5001/api/health

# Run scrapers in production
docker exec jps-web python -m scripts.scrapers.run_scraper --source "DHS"

# Access shell
docker exec -it jps-web /bin/bash
```

### Cloudflare Tunnel Setup
1. Create tunnel in Cloudflare Zero Trust dashboard
2. Get tunnel token
3. Run `./launch.sh --prod` and provide token when prompted
4. Or manually add to .env: `CLOUDFLARE_TUNNEL_TOKEN=your-token`
5. Deploy with: `docker-compose --profile cloudflare up -d`

### Production Security
- SECRET_KEY: Auto-generated 64-character hex string
- Session cookies: Secure, HTTPOnly, SameSite=Lax
- CORS: Restricted to configured domains
- Debug mode: Disabled
- SQLite: WAL mode for better concurrency

## Performance Tips

### Database
```bash
# .env optimizations
SQLITE_JOURNAL_MODE=WAL
SQLITE_SYNCHRONOUS=NORMAL
SQLITE_CACHE_SIZE=-64000
```

### Frontend
- Virtual scrolling for large datasets
- Production build: `npm run build`

### Scrapers
- Concurrent execution
- Retry with exponential backoff
- Configure timeout in .env

## Additional Documentation

For detailed information, see:
- `docs/ARCHITECTURE.md` - System design
- `docs/TESTING.md` - Comprehensive testing guide
- `docs/DATA_MAPPING_GUIDE.md` - Field mappings
- `docs/SCRAPER_QUIRKS.md` - Agency-specific issues
- `README.md` - Project overview
- We are following a test-driven development (TDD) approach, so do not create mock implementations or artificial stand-ins for functionality. All tests must use real-world, representative input/output pairs that reflect actual usage scenarios, ensuring that the code is validated against realistic conditions rather than simulated ones.