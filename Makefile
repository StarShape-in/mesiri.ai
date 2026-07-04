# Mesiri.ai — repository-standard developer commands (Python runtime).
#
# These wrap `uv` and `docker compose`. On Windows, run under Git Bash or WSL,
# or invoke the underlying commands directly (see each target).
.DEFAULT_GOAL := help
.PHONY: help venv install dev down logs test test-integration lint typecheck migrate m1-golden

# Import roots for scripts invoked as `python -m` (pytest uses pyproject config).
export PYTHONPATH := shared/contracts/src:platform/ai/src:backend/src:apps/whatsapp-assistant/src

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

venv: ## Create the local virtualenv
	uv venv --python 3.10

install: ## Install runtime + dev + infra + provider dependencies
	uv pip install -e ".[dev,infra,providers]"

dev: ## Start the local stack (Postgres + Redis)
	docker compose up -d

down: ## Stop the local stack
	docker compose down

logs: ## Tail the local stack logs
	docker compose logs -f

test: ## Run the full test suite against fakes (no docker, no external APIs)
	uv run pytest

test-integration: ## Run integration tests against the live docker stack
	uv run pytest -m integration

lint: ## Lint the Python runtime
	uv run ruff check .

typecheck: ## Type-check the Python runtime
	uv run mypy backend/src platform/ai/src shared/contracts/src

migrate: ## Apply database migrations to the local Postgres
	uv run alembic -c backend/alembic.ini upgrade head

m1-golden: ## Run the M1 "Infrastructure Alive" golden scenario
	uv run python -m mesiri.scripts.run_m1_golden_scenario
