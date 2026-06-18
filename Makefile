# DataBossX developer/operator shortcuts.
# Usage: make <target>   (run `make help` to list targets)

PYTHON ?= python3

.PHONY: help setup dev-setup doctor test lint security backup run-backend run-frontend clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Install full backend requirements
	$(PYTHON) -m pip install -r requirements.txt

dev-setup: ## Install lean test/dev dependencies
	$(PYTHON) -m pip install -r requirements-dev.txt

doctor: ## Run environment health check
	$(PYTHON) scripts/doctor.py

test: ## Run the unit/integration test suite
	$(PYTHON) -m pytest -q

lint: ## Run the flake8 syntax-error gate (matches CI)
	$(PYTHON) -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

security: ## Run dependency + secret hygiene scan
	$(PYTHON) scripts/security_scan.py

backup: ## Create a timestamped local source backup
	$(PYTHON) scripts/backup_project.py

run-backend: ## Start the FastAPI backend (port 8001)
	cd backend && $(PYTHON) -m uvicorn server:app --reload --port 8001

run-frontend: ## Start the React frontend (port 3000)
	cd frontend && yarn install && yarn start

clean: ## Remove Python caches
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
