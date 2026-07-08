"""PostgreSQL implementation of workflows.ports.WorkflowInstanceRepository.

Implements the abstraction owned by the workflow layer (workflows/ports.py) —
this is the only file permitted to hold SQL for workflow_instances (same
capability-boundary pattern as backend/postgres/actor.py). organization_id and
user_id are plain strings here (matching migration 0170_workflows_fix_instance_id_types) because
ContextResolver resolves them against context_organizations/context_users,
which use arbitrary string ids, not the control-plane UUID tables.
"""

from __future__ import annotations

import os
import uuid

from mesiri_contracts.assistant.workflow_state import WorkflowState


def _build_engine():
    # SQLAlchemy imported lazily to avoid the platform/ shadow-package issue
    # during test collection (see pyproject notes in the repo root).
    from sqlalchemy.ext.asyncio import create_async_engine

    host = os.environ.get("MESIRI_POSTGRES__HOST", "localhost")
    port = os.environ.get("MESIRI_POSTGRES__PORT", "5432")
    user = os.environ.get("MESIRI_POSTGRES__USER", "mesiri")
    password = os.environ.get("MESIRI_POSTGRES__PASSWORD", "mesiri_local_dev")
    database = os.environ.get("MESIRI_POSTGRES__DATABASE", "mesiri")
    dsn = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    return create_async_engine(dsn, echo=False, pool_pre_ping=True)


class PostgresWorkflowInstanceRepository:
    """Satisfies workflows.ports.WorkflowInstanceRepository by writing workflow_instances.

    Lifecycle: create once at process startup. The engine is built lazily on
    the first save() call so unit tests that never touch the DB don't need
    sqlalchemy.
    """

    def __init__(self, engine=None) -> None:
        self._engine = engine

    def _get_engine(self):
        if self._engine is None:
            self._engine = _build_engine()
        return self._engine

    async def save(self, state: WorkflowState) -> None:
        from sqlalchemy import text

        async with self._get_engine().begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO workflow_instances "
                    "(id, organization_id, user_id, workflow_key, phase, state, correlation_id, status) "
                    "VALUES (:id, :organization_id, :user_id, :workflow_key, :phase, :state::jsonb, "
                    ":correlation_id, :status)"
                ),
                {
                    "id": uuid.UUID(state.workflow_instance_id),
                    "organization_id": state.organization_id,
                    "user_id": state.user_id,
                    "workflow_key": state.workflow_key.value,
                    "phase": state.phase.value,
                    "state": state.model_dump_json(),
                    "correlation_id": state.correlation_id,
                    "status": "active",
                },
            )
