.PHONY: help install dev db-up db-down db-reset scrape test lint format clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies with uv
	uv pip install -e .

dev: ## Install with dev dependencies
	uv pip install -e ".[dev]"

db-up: ## Start PostgreSQL with Docker
	docker-compose up -d postgres
	@echo "Waiting for PostgreSQL to be ready..."
	@sleep 3
	@docker-compose exec -T postgres pg_isready -U hkjc_user -d hkjc_racing || echo "Database starting..."

db-down: ## Stop PostgreSQL
	docker-compose down

db-reset: ## Reset database (WARNING: deletes all data)
	docker-compose down -v
	docker-compose up -d postgres
	@echo "Waiting for PostgreSQL to be ready..."
	@sleep 3
	uv run python database.py

db-logs: ## View database logs
	docker-compose logs -f postgres

db-shell: ## Open PostgreSQL shell
	docker-compose exec postgres psql -U hkjc_user -d hkjc_racing

pgadmin: ## Start pgAdmin (web UI at http://localhost:5050)
	docker-compose --profile tools up -d pgadmin
	@echo "pgAdmin available at http://localhost:5050"
	@echo "Email: admin@hkjc.local, Password: admin"

scrape: ## Scrape data (usage: make scrape DATE=2025/12/23)
	@if [ -z "$(DATE)" ]; then \
		echo "Error: DATE is required. Usage: make scrape DATE=2025/12/23"; \
		exit 1; \
	fi
	uv run python main.py $(DATE)

dry-run: ## Dry run scrape (usage: make dry-run DATE=2025/12/23)
	@if [ -z "$(DATE)" ]; then \
		echo "Error: DATE is required. Usage: make dry-run DATE=2025/12/23"; \
		exit 1; \
	fi
	uv run python main.py $(DATE) --dry-run

init-db: ## Initialize database tables
	uv run python database.py

test: ## Run tests
	uv run pytest

lint: ## Run linter (ruff)
	uv run ruff check .

format: ## Format code (ruff)
	uv run ruff format .

clean: ## Clean temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

sync: ## Sync dependencies with uv
	uv pip sync

lock: ## Update uv.lock (if using)
	uv pip compile pyproject.toml -o requirements.txt
