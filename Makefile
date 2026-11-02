# Root Makefile - includes CI testing commands
# This file simply includes the CI testing Makefile for convenience

# Include the CI testing Makefile
include ci-test/Makefile

# Add any root-level specific targets here
.PHONY: help-root
help-root:
	@echo "JPS Prospect Aggregate - Project Commands"
	@echo ""
	@echo "This Makefile includes all CI testing commands from ci-test/Makefile"
	@echo "Run 'make help' to see all available commands"
	@echo ""
	@echo "Quick commands:"
	@echo "  make test        - Run full CI test suite"
	@echo "  make test-python - Run Python tests only"
	@echo "  make test-frontend - Run frontend tests only"
