"""PostgreSQL implementation of workflows.ports.WorkflowInstanceRepository.

Implements the abstraction owned by the workflow layer (workflows/ports.py) —
this is the only file permitted to hold SQL for workflow_instances (same
capability-boundary pattern as backend/postgres/actor.py). organization_id and
user_id are canonical Control Plane UUIDs (migration 0195).
"""

from __future__ import annotations

import os
import uuid

from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2
from workflows.ports import LoadedWorkflowInstance, SingleActiveConflict


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

    async def save(self, state: WorkflowStateV2) -> None:
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError

        try:
            async with self._get_engine().begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO workflow_instances "
                        "(id, organization_id, user_id, workflow_key, phase, state, "
                        "correlation_id, status, version) "
                        "VALUES (:id, :organization_id, :user_id, :workflow_key, :phase, "
                        "CAST(:state AS jsonb), :correlation_id, :status, 0)"
                    ),
                    {
                        "id": uuid.UUID(state.workflow_instance_id),
                        "organization_id": uuid.UUID(state.organization_id),
                        "user_id": uuid.UUID(state.user_id),
                        "workflow_key": state.workflow_key.value,
                        "phase": state.phase.value,
                        "state": state.model_dump_json(),
                        "correlation_id": state.correlation_id,
                        "status": "active",
                    },
                )
        except IntegrityError as exc:
            # The partial unique index (one awaiting-confirmation per user) is the
            # hard single-active guarantee. Surface it as a domain conflict so the
            # runtime can turn it into a BLOCKED result.
            raise SingleActiveConflict(
                f"user {state.user_id} already has an awaiting-confirmation workflow"
            ) from exc

    async def get_awaiting_confirmation(self, user_id: str) -> LoadedWorkflowInstance | None:
        from sqlalchemy import text

        async with self._get_engine().connect() as conn:
            row = (
                (
                    await conn.execute(
                        text(
                            "SELECT state, version FROM workflow_instances "
                            "WHERE user_id = :user_id AND phase = 'awaiting_confirmation' "
                            "AND status = 'active' "
                            "ORDER BY created_at DESC LIMIT 1"
                        ),
                        {"user_id": uuid.UUID(user_id)},
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        state = WorkflowStateV2.model_validate_json(_as_json_text(row["state"]))
        return LoadedWorkflowInstance(state=state, version=int(row["version"]))

    async def transition(
        self, workflow_instance_id: str, expected_version: int, new_state: WorkflowStateV2
    ) -> bool:
        """Transition in this repository's own transaction (the normal M7 path)."""
        async with self._get_engine().begin() as conn:
            return await transition_on_connection(
                conn, workflow_instance_id, expected_version, new_state
            )


async def transition_on_connection(
    conn, workflow_instance_id: str, expected_version: int, new_state: WorkflowStateV2
) -> bool:
    """The phase-transition UPDATE, against an externally-supplied connection.

    Extracted so the M8 Material execution transaction can complete/reject a
    workflow (phase -> COMPLETED/EXECUTION_REJECTED) atomically alongside the
    domain write — that requires running on the *same* open connection as the
    material/outbox/idempotency inserts, not a second, independent transaction.
    `PostgresWorkflowInstanceRepository.transition()` (the normal M7 confirm/
    reject/cancel path) is a thin wrapper that opens its own transaction and
    calls this same function — no SQL is duplicated between the two call sites.
    """
    from sqlalchemy import text

    terminal = new_state.phase.value  # confirmed | rejected | cancelled | completed | execution_rejected
    status = "completed" if terminal == "confirmed" else terminal
    result = await conn.execute(
        text(
            "UPDATE workflow_instances "
            "SET phase = :phase, status = :status, state = CAST(:state AS jsonb), "
            "version = version + 1, updated_at = now() "
            "WHERE id = :id AND version = :expected_version"
        ),
        {
            "id": uuid.UUID(workflow_instance_id),
            "expected_version": expected_version,
            "phase": new_state.phase.value,
            "status": status,
            "state": new_state.model_dump_json(),
        },
    )
    return result.rowcount == 1


async def get_by_id_on_connection(conn, workflow_instance_id: str) -> LoadedWorkflowInstance | None:
    """Read current state+version for one instance, against a supplied connection,
    regardless of phase. Used by the M8 Application Handler to learn the current
    version before transitioning CONFIRMED -> COMPLETED/EXECUTION_REJECTED (the
    version was already bumped once by M7's own CONFIRMED transition)."""
    from sqlalchemy import text

    row = (
        await conn.execute(
            text("SELECT state, version FROM workflow_instances WHERE id = :id"),
            {"id": uuid.UUID(workflow_instance_id)},
        )
    ).mappings().first()
    if row is None:
        return None
    state = WorkflowStateV2.model_validate_json(_as_json_text(row["state"]))
    return LoadedWorkflowInstance(state=state, version=int(row["version"]))


async def list_confirmed_by_workflow_keys(
    db, workflow_keys: list[str]
) -> list[LoadedWorkflowInstance]:
    """All CONFIRMED instances matching the given workflow_key values — the
    recovery sweep's read. Scoped by workflow_key deliberately: workflow_instances
    is generic, and a future Expense/Equipment/Labour executor must never have
    its confirmed rows swept up and deserialized by the Material recovery path.

    `db` is a PostgresDatabase (or anything exposing the same `.transaction()`
    async context manager) — matches how every other M8 read/write obtains its
    connection, rather than reaching for a raw engine.
    """
    from sqlalchemy import text

    async with db.transaction() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT state, version FROM workflow_instances "
                    "WHERE phase = 'confirmed' AND workflow_key = ANY(:workflow_keys::text[])"
                ),
                {"workflow_keys": workflow_keys},
            )
        ).mappings().all()
    return [
        LoadedWorkflowInstance(
            state=WorkflowStateV2.model_validate_json(_as_json_text(row["state"])),
            version=int(row["version"]),
        )
        for row in rows
    ]


def _as_json_text(value) -> str:
    """asyncpg returns JSONB as str; normalize to a JSON text for pydantic."""
    import json

    return value if isinstance(value, str) else json.dumps(value)
