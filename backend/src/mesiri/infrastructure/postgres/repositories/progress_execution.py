"""PostgreSQL implementation of mesiri.application.progress.repository.ProgressExecutionRepository.

The only file permitted to hold SQL for activities/activity_quantities/
progress_updates execution (capability-boundary convention, mirrors
material_execution.py and labour_execution.py). Every method takes an
externally-supplied connection — the Application Handler opens the one
transaction; this repository never commits.

Emits generic `outbox_events` rows for both Activity creation and Progress
Update append, the same mechanism every other operational module already
uses. **Not yet registered** in
`mesiri.events.consumers.timeline_projector.AGGREGATE_TABLES` — that
registration is Phase 6.0 of docs/execution/DAILY_REPORTING_PLAN.md, tracked
there alongside the pre-existing Labour/Finance projection gaps. Note for
whoever does that registration: `activities` uses `activity_date` /
`started_at` rather than the `occurred_date` / `occurred_time` names
`AGGREGATE_TABLES`'s other entries use — either alias those columns in the
registration or extend the projector to accept a column-name mapping per
aggregate type, whichever is less invasive at the time.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

from mesiri.application.progress.repository import ProgressExecutionRepository
from mesiri.infrastructure.postgres.workflow_instance import (
    get_by_id_on_connection,
    transition_on_connection,
)
from mesiri_contracts.application.commands.progress import (
    AddProgressUpdateCommand,
    CreateActivityCommand,
)
from mesiri_contracts.application.results.execution_result import (
    ExecutionResult,
    ExecutionStatus,
    as_replay,
)
from mesiri_contracts.context.enums import WorkflowPhase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


def _optional_uuid(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value is not None else None


class PostgresProgressExecutionRepository(ProgressExecutionRepository):
    async def check_idempotency(self, conn: AsyncConnection, key: str) -> ExecutionResult | None:
        from sqlalchemy import text

        row = (
            (
                await conn.execute(
                    text("SELECT status, result FROM idempotency_keys WHERE key = :key"),
                    {"key": key},
                )
            )
            .mappings()
            .first()
        )
        if row is None or row["status"] != "completed" or row["result"] is None:
            return None
        result_json = row["result"]
        if not isinstance(result_json, str):
            result_json = json.dumps(result_json)
        return ExecutionResult.model_validate_json(result_json)

    async def _try_claim(self, conn: AsyncConnection, idempotency_key: str, command_type: str) -> bool:
        """INSERT ... ON CONFLICT DO NOTHING — True if this call won the claim."""
        from sqlalchemy import text

        claimed = (
            await conn.execute(
                text(
                    "INSERT INTO idempotency_keys (key, command_type, status) "
                    "VALUES (:key, :command_type, 'in_progress') "
                    "ON CONFLICT (key) DO NOTHING RETURNING key"
                ),
                {"key": idempotency_key, "command_type": command_type},
            )
        ).first()
        return claimed is not None

    async def persist_create_activity_success(
        self, conn: AsyncConnection, cmd: CreateActivityCommand
    ) -> ExecutionResult:
        from sqlalchemy import text

        if not await self._try_claim(conn, cmd.idempotency_key, "create_activity"):
            existing = await self.check_idempotency(conn, cmd.idempotency_key)
            assert existing is not None
            return as_replay(existing)

        organization_id = uuid.UUID(cmd.organization_id)
        project_id = _optional_uuid(cmd.project_id)
        site_id = _optional_uuid(cmd.site_id)
        created_by = uuid.UUID(cmd.created_by)

        if project_id is None or site_id is None:
            # domains/progress/validation.py already rejects this before
            # persist_create_activity_success is ever called; defensive
            # guard against calling this method directly with an unvalidated
            # command, matching material_execution.py's equivalent check.
            raise RuntimeError("project_id and site_id are required to persist an activity")

        activity_id = uuid.uuid4()
        await conn.execute(
            text(
                "INSERT INTO activities "
                "(id, organization_id, project_id, site_id, work_package_id, location_id, "
                "work_type, activity_date, started_at, ended_at, status, narrative, contractor, "
                "reported_by_user_id, source, correlation_id) "
                "VALUES (:id, :organization_id, :project_id, :site_id, :work_package_id, :location_id, "
                ":work_type, :activity_date, :started_at, :ended_at, 'IN_PROGRESS', :narrative, "
                ":contractor, :reported_by_user_id, :source, :correlation_id)"
            ),
            {
                "id": activity_id,
                "organization_id": organization_id,
                "project_id": project_id,
                "site_id": site_id,
                "work_package_id": _optional_uuid(cmd.work_package_id),
                "location_id": _optional_uuid(cmd.location_id),
                "work_type": cmd.work_type,
                "activity_date": cmd.activity_date,
                "started_at": cmd.started_at,
                "ended_at": cmd.ended_at,
                "narrative": cmd.narrative,
                "contractor": cmd.contractor,
                "reported_by_user_id": created_by,
                "source": cmd.source,
                "correlation_id": cmd.correlation_id,
            },
        )

        for q in cmd.quantities:
            await conn.execute(
                text(
                    "INSERT INTO activity_quantities "
                    "(id, activity_id, work_type, unit_id, quantity, measurement_type) "
                    "VALUES (:id, :activity_id, :work_type, :unit_id, :quantity, :measurement_type)"
                ),
                {
                    "id": uuid.uuid4(),
                    "activity_id": activity_id,
                    "work_type": q.work_type,
                    "unit_id": uuid.UUID(q.unit_id) if q.unit_id else None,
                    "quantity": q.quantity,
                    "measurement_type": q.measurement_type,
                },
            )

        payload = {
            "activity_date": cmd.activity_date.isoformat(),
            "occurred_date_source": cmd.occurred_date_source,
            "source": cmd.source,
            "work_type": cmd.work_type,
            "quantity_count": len(cmd.quantities),
        }
        await conn.execute(
            text(
                "INSERT INTO outbox_events "
                "(id, aggregate_type, aggregate_id, event_type, payload, correlation_id) "
                "VALUES (:id, :aggregate_type, :aggregate_id, :event_type, "
                "CAST(:payload AS jsonb), :correlation_id)"
            ),
            {
                "id": uuid.uuid4(),
                "aggregate_type": "activity",
                "aggregate_id": activity_id,
                "event_type": "ActivityCreated",
                "payload": json.dumps(payload),
                "correlation_id": cmd.correlation_id,
            },
        )

        result = ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=cmd.idempotency_key,
            # Shared contract field name (see labour_execution.py's identical
            # comment) — here it is activities.id.
            material_row_id=str(activity_id),
        )
        await conn.execute(
            text(
                "UPDATE idempotency_keys "
                "SET status = 'completed', result = CAST(:result AS jsonb), completed_at = now() "
                "WHERE key = :key"
            ),
            {"result": result.model_dump_json(), "key": cmd.idempotency_key},
        )

        await self._transition(conn, cmd.idempotency_key, WorkflowPhase.COMPLETED)
        return result

    async def persist_add_progress_update_success(
        self, conn: AsyncConnection, cmd: AddProgressUpdateCommand
    ) -> ExecutionResult:
        from sqlalchemy import text

        if not await self._try_claim(conn, cmd.idempotency_key, "add_progress_update"):
            existing = await self.check_idempotency(conn, cmd.idempotency_key)
            assert existing is not None
            return as_replay(existing)

        activity_id = uuid.UUID(cmd.activity_id)
        created_by = uuid.UUID(cmd.created_by)

        update_id = uuid.uuid4()
        await conn.execute(
            text(
                "INSERT INTO progress_updates "
                "(id, activity_id, occurred_at, update_kind, narrative, quantity, unit_id, "
                "reported_by_user_id, source, correlation_id) "
                "VALUES (:id, :activity_id, :occurred_at, :update_kind, :narrative, :quantity, "
                ":unit_id, :reported_by_user_id, :source, :correlation_id)"
            ),
            {
                "id": update_id,
                "activity_id": activity_id,
                "occurred_at": cmd.occurred_at,
                "update_kind": cmd.update_kind,
                "narrative": cmd.narrative,
                "quantity": cmd.quantity,
                "unit_id": uuid.UUID(cmd.unit_id) if cmd.unit_id else None,
                "reported_by_user_id": created_by,
                "source": cmd.source,
                "correlation_id": cmd.correlation_id,
            },
        )

        # STARTED/PAUSED/RESUMED/COMPLETED move the parent Activity's status.
        # This is the one field on activities this repository ever mutates
        # outside of creation -- it is a status transition, not a correction
        # (ADR-D14 governs corrections; this is ordinary lifecycle movement,
        # same as Work Package status), so no activity_corrections row is
        # written for it.
        _STATUS_BY_KIND = {
            "STARTED": "IN_PROGRESS",
            "RESUMED": "IN_PROGRESS",
            "PAUSED": "STOPPED",
            "COMPLETED": "COMPLETED",
        }
        new_status = _STATUS_BY_KIND.get(cmd.update_kind)
        if new_status is not None:
            await conn.execute(
                text("UPDATE activities SET status = :status, updated_at = now() WHERE id = :id"),
                {"status": new_status, "id": activity_id},
            )

        payload = {
            "update_kind": cmd.update_kind,
            "occurred_at": cmd.occurred_at.isoformat(),
            "quantity": str(cmd.quantity) if cmd.quantity is not None else None,
            "source": cmd.source,
        }
        await conn.execute(
            text(
                "INSERT INTO outbox_events "
                "(id, aggregate_type, aggregate_id, event_type, payload, correlation_id) "
                "VALUES (:id, :aggregate_type, :aggregate_id, :event_type, "
                "CAST(:payload AS jsonb), :correlation_id)"
            ),
            {
                "id": uuid.uuid4(),
                "aggregate_type": "activity",
                "aggregate_id": activity_id,
                "event_type": "ActivityProgressUpdateAdded",
                "payload": json.dumps(payload),
                "correlation_id": cmd.correlation_id,
            },
        )

        result = ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=cmd.idempotency_key,
            # Here it is progress_updates.id -- the row this confirmation
            # actually created, not the parent activity.
            material_row_id=str(update_id),
        )
        await conn.execute(
            text(
                "UPDATE idempotency_keys "
                "SET status = 'completed', result = CAST(:result AS jsonb), completed_at = now() "
                "WHERE key = :key"
            ),
            {"result": result.model_dump_json(), "key": cmd.idempotency_key},
        )

        await self._transition(conn, cmd.idempotency_key, WorkflowPhase.COMPLETED)
        return result

    async def persist_rejection(
        self,
        conn: AsyncConnection,
        idempotency_key: str,
        command_type: str,
        reasons: list[str],
    ) -> ExecutionResult:
        from sqlalchemy import text

        if not await self._try_claim(conn, idempotency_key, command_type):
            existing = await self.check_idempotency(conn, idempotency_key)
            assert existing is not None
            return as_replay(existing)

        result = ExecutionResult(
            status=ExecutionStatus.REJECTED,
            idempotency_key=idempotency_key,
            rejection_reasons=reasons,
        )
        await conn.execute(
            text(
                "UPDATE idempotency_keys "
                "SET status = 'completed', result = CAST(:result AS jsonb), completed_at = now() "
                "WHERE key = :key"
            ),
            {"result": result.model_dump_json(), "key": idempotency_key},
        )

        await self._transition(conn, idempotency_key, WorkflowPhase.EXECUTION_REJECTED)
        return result

    async def _transition(
        self, conn: AsyncConnection, workflow_instance_id: str, new_phase: WorkflowPhase
    ) -> None:
        """Move workflow_instances to `new_phase` on the same connection as the
        domain write, using the current version read fresh from this connection."""
        loaded = await get_by_id_on_connection(conn, workflow_instance_id)
        if loaded is None:
            return  # nothing to transition (shouldn't happen; defensive, not fatal)
        new_state = loaded.state.model_copy(update={"phase": new_phase})
        await transition_on_connection(conn, workflow_instance_id, loaded.version, new_state)
