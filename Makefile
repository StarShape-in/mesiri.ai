# Mesiri.ai — repository-standard developer commands (Python runtime).
#
# These wrap `uv` and `docker compose`. On Windows, run under Git Bash or WSL,
# or invoke the underlying commands directly (see each target).
.DEFAULT_GOAL := help
.PHONY: help venv install dev down logs test test-integration lint typecheck migrate m1-golden m4-gate project-timeline event-consumers notification-checks notification-send dpr-generate dpr-render

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
	# Target the integration path directly: a whole-tree collection would import
	# the repo's top-level `platform/` dir as a namespace package, shadowing the
	# stdlib `platform` module that SQLAlchemy imports.
	uv run pytest backend/tests/integration -m integration

lint: ## Lint the Python runtime
	uv run ruff check .

typecheck: ## Type-check the Python runtime
	uv run mypy backend/src platform/ai/src shared/contracts/src

migrate: ## Apply database migrations to the local Postgres
	uv run alembic -c backend/alembic.ini upgrade head

m1-golden: ## Run the M1 "Infrastructure Alive" golden scenario
	uv run python -m mesiri.scripts.run_m1_golden_scenario

project-timeline: ## Drain outbox_events into timeline_entries (run manually or via cron)
	uv run python -m mesiri.scripts.project_timeline_events

event-consumers: ## Drain outbox_events for every #14 Event Bus consumer (run manually or via cron)
	uv run python -m mesiri.scripts.run_event_consumers

notification-checks: ## Run #9 Notifications' scheduled checks and queue due notifications (run manually or via cron)
	uv run python -m mesiri.scripts.run_notification_checks

notification-send: ## Send #9 Notifications' queued 'pending' rows over WhatsApp (run manually or via cron)
	cd apps/whatsapp-assistant/src && PYTHONPATH=$(PYTHONPATH) uv run python -m runtime.send_pending_notifications

dpr-generate: ## Assemble/refresh today's #16 DPR draft for every site with activity (run manually or via cron)
	uv run python -m mesiri.scripts.run_dpr_generation

dpr-render: ## Render #16 DPR versions with a payload but no PDF yet (run manually or via cron)
	cd apps/whatsapp-assistant/src && PYTHONPATH=$(PYTHONPATH) uv run python -m runtime.render_pending_dpr_pdfs

m4-gate: ## Run the M4 "Context Foundation" golden scenario + M4 scenarios
	uv run python scripts/run_m4_golden_scenario.py
	uv run pytest -m scenario scenarios/m4 apps/whatsapp-assistant/tests/unit/test_m4_context.py
