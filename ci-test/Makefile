# JPS Prospect Aggregate - Makefile for local CI testing
.PHONY: help test test-ci test-python test-frontend test-integration test-e2e test-all fix-types clean

# Default target - show help
help:
	@echo "JPS Prospect Aggregate - Local CI Testing"
	@echo ""
	@echo "Available commands:"
	@echo "  make test-ci         - Run full CI test suite locally (Python + Frontend + Integration)"
	@echo "  make test-python     - Run only Python tests with linting and type checking"
	@echo "  make test-frontend   - Run only frontend tests with TypeScript checking"
	@echo "  make test-integration- Run only integration tests"
	@echo "  make test-e2e        - Run end-to-end tests (requires running services)"
	@echo "  make test-all        - Run all tests including E2E"
	@echo "  make fix-types       - Fix TypeScript type errors in frontend"
	@echo "  make clean           - Clean test artifacts and caches"
	@echo ""
	@echo "Quick start:"
	@echo "  make test-ci         - Recommended for pre-commit testing"

# Run full CI test suite
test-ci:
	@echo "Running full CI test suite..."
	@ci-test/test-ci-local.sh

# Run tests (alias for test-ci)
test: test-ci

# Run only Python tests
test-python:
	@echo "Running Python tests..."
	@ci-test/test-ci-local.sh --python-only

# Run only frontend tests
test-frontend:
	@echo "Running frontend tests..."
	@ci-test/test-ci-local.sh --frontend-only

# Run only integration tests
test-integration:
	@echo "Running integration tests..."
	@ci-test/test-ci-local.sh --integration-only

# Run E2E tests
test-e2e:
	@echo "Running E2E tests..."
	@ci-test/test-ci-local.sh --e2e

# Run all tests including E2E
test-all:
	@echo "Running all tests including E2E..."
	@ci-test/test-ci-local.sh --all

# Fix TypeScript type errors
fix-types:
	@echo "Attempting to fix TypeScript errors..."
	@cd frontend-react && npx tsc --noEmit --project tsconfig.test.json || true
	@echo "Running prettier on test files..."
	@cd frontend-react && npx prettier --write "src/**/*.test.{ts,tsx}"

# Clean test artifacts
clean:
	@echo "Cleaning test artifacts..."
	@rm -rf htmlcov/
	@rm -rf frontend-react/coverage/
	@rm -rf .pytest_cache/
	@rm -rf frontend-react/node_modules/.vitest/
	@rm -f .coverage
	@rm -f coverage.xml
	@rm -f .env.test
	@echo "Clean complete!"

# Build Docker images for CI testing
build-ci:
	@echo "Building CI test containers..."
	@docker-compose -f ci-test/docker-compose.test.yml build

# Stop and remove CI test containers
stop-ci:
	@echo "Stopping CI test containers..."
	@docker-compose -f ci-test/docker-compose.test.yml down -v

# Run Python linting only
lint-python:
	@echo "Running Python linting..."
	@ruff check app/ --output-format=text
	@ruff format app/ --check

# Run frontend linting only
lint-frontend:
	@echo "Running frontend linting..."
	@cd frontend-react && npm run lint

# Run type checking for Python
type-check-python:
	@echo "Running Python type checking..."
	@mypy app/ --ignore-missing-imports --disallow-untyped-defs

# Run type checking for frontend
type-check-frontend:
	@echo "Running frontend type checking..."
	@cd frontend-react && npx tsc --noEmit

# Install act for GitHub Actions local testing
install-act:
	@echo "Installing act for GitHub Actions local testing..."
	@if command -v brew >/dev/null 2>&1; then \
		brew install act; \
	else \
		echo "Please install act manually from https://github.com/nektos/act"; \
	fi

# Run GitHub Actions locally with act
test-with-act:
	@echo "Running GitHub Actions locally with act..."
	@if command -v act >/dev/null 2>&1; then \
		act -P ubuntu-latest=catthehacker/ubuntu:act-latest; \
	else \
		echo "act is not installed. Run 'make install-act' first."; \
	fi
