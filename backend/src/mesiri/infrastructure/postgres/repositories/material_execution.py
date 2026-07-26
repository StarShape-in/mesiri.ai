"""PostgreSQL implementation of mesiri.application.materials.repository.MaterialExecutionRepository.

The only file permitted to hold SQL for material_receipts/material_usage
execution (capability-boundary convention). Every method takes an externally-
supplied connection — the Application Handler opens the one transaction
(via PostgresDatabase.transaction()); this repository never commits.

Reuses backend.postgres.workflow_instance's connection-scoped helpers
(transition_on_connection, get_by_id_on_connection) rather than duplicating
workflow_instances SQL here — that table's SQL stays owned by one file.
"""

from __future__ import annotations

import datetime
import json
import uuid
from typing import TYPE_CHECKING

from mesiri.application.materials.repository import MaterialCommand, MaterialExecutionRepository
from mesiri.domains.materials.posting import post_material_movement
from mesiri.infrastructure.postgres.workflow_instance import (
    get_by_id_on_connection,
    transition_on_connection,
)
from mesiri_contracts.application.commands.material import (
    RecordMaterialReceiptCommand,
)
from mesiri_contracts.application.results.execution_result import (
    ExecutionResult,
    ExecutionStatus,
    as_replay,
)
from mesiri_contracts.context.enums import WorkflowPhase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


def _command_type(cmd: MaterialCommand) -> str:
    return (
        "record_material_receipt"
        if isinstance(cmd, RecordMaterialReceiptCommand)
        else "record_material_usage"
    )


def _optional_uuid(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value is not None else None


class PostgresMaterialExecutionRepository(MaterialExecutionRepository):
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

    async def _try_claim(self, conn: AsyncConnection, cmd: MaterialCommand) -> bool:
        """INSERT ... ON CONFLICT DO NOTHING — True if this call won the claim."""
        from sqlalchemy import text

        claimed = (
            await conn.execute(
                text(
                    "INSERT INTO idempotency_keys (key, command_type, status) "
                    "VALUES (:key, :command_type, 'in_progress') "
                    "ON CONFLICT (key) DO NOTHING RETURNING key"
                ),
                {"key": cmd.idempotency_key, "command_type": _command_type(cmd)},
            )
        ).first()
        return claimed is not None

    async def persist_success(self, conn: AsyncConnection, cmd: MaterialCommand) -> ExecutionResult:
        from sqlalchemy import text

        if not await self._try_claim(conn, cmd):
            # A concurrent transaction already claimed this key. Postgres's row
            # lock on the conflicting INSERT means this call only reaches here
            # after the winner's transaction has committed (or rolled back) --
            # so the row is already visible as completed by the time we look.
            # This call did not perform the write, so a cached SUCCEEDED is
            # reported as ALREADY_EXECUTED, not SUCCEEDED again.
            existing = await self.check_idempotency(conn, cmd.idempotency_key)
            assert existing is not None
            return as_replay(existing)

        if cmd.material_id is None or cmd.unit_id is None:
            raise RuntimeError(
                "persist_success called with unresolved material_id/unit_id — "
                "the Handler must resolve these before calling persist_success"
            )
        material_id = uuid.UUID(cmd.material_id)
        unit_id = uuid.UUID(cmd.unit_id)
        project_id = _optional_uuid(cmd.project_id)
        site_id = _optional_uuid(cmd.site_id)
        occurred_at = datetime.datetime.combine(cmd.occurred_date, datetime.time.min)

        row_id = uuid.uuid4()
        if isinstance(cmd, RecordMaterialReceiptCommand):
            await conn.execute(
                text(
                    "INSERT INTO material_receipts "
                    "(id, organization_id, project_id, site_id, material_name, quantity, unit, "
                    "unit_id, material_id, supplier, occurred_date, occurred_date_source, "
                    "correlation_id, created_by) "
                    "VALUES (:id, :organization_id, :project_id, :site_id, :material_name, "
                    ":quantity, :unit, :unit_id, :material_id, :supplier, :occurred_date, "
                    ":occurred_date_source, :correlation_id, :created_by)"
                ),
                {
                    "id": row_id,
                    "organization_id": uuid.UUID(cmd.organization_id),
                    "project_id": project_id,
                    "site_id": site_id,
                    "material_name": cmd.material_name,
                    "quantity": cmd.quantity,
                    "unit": cmd.unit,
                    "unit_id": unit_id,
                    "material_id": material_id,
                    "supplier": cmd.supplier,
                    "occurred_date": cmd.occurred_date,
                    "occurred_date_source": cmd.occurred_date_source,
                    "correlation_id": cmd.correlation_id,
                    "created_by": uuid.UUID(cmd.created_by),
                },
            )
            aggregate_type, event_type = "material_receipt", "MaterialReceived"
            movement_type, source_type = "RECEIPT", "material_receipt"
        else:
            await conn.execute(
                text(
                    "INSERT INTO material_usage "
                    "(id, organization_id, project_id, site_id, material_name, quantity, unit, "
                    "unit_id, material_id, work_item, occurred_date, occurred_date_source, "
                    "correlation_id, created_by) "
                    "VALUES (:id, :organization_id, :project_id, :site_id, :material_name, "
                    ":quantity, :unit, :unit_id, :material_id, :work_item, :occurred_date, "
                    ":occurred_date_source, :correlation_id, :created_by)"
                ),
                {
                    "id": row_id,
                    "organization_id": uuid.UUID(cmd.organization_id),
                    "project_id": project_id,
                    "site_id": site_id,
                    "material_name": cmd.material_name,
                    "quantity": cmd.quantity,
                    "unit": cmd.unit,
                    "unit_id": unit_id,
                    "material_id": material_id,
                    "work_item": cmd.work_item,
                    "occurred_date": cmd.occurred_date,
                    "occurred_date_source": cmd.occurred_date_source,
                    "correlation_id": cmd.correlation_id,
                    "created_by": uuid.UUID(cmd.created_by),
                },
            )
            aggregate_type, event_type = "material_usage", "MaterialUsed"
            movement_type, source_type = "ISSUE", "material_usage"

        if project_id is None:
            raise RuntimeError("project_id is required to post a material_movement")
        await post_material_movement(
            conn,
            movement_type=movement_type,
            material_id=material_id,
            unit_id=unit_id,
            quantity=cmd.quantity,
            organization_id=uuid.UUID(cmd.organization_id),
            project_id=project_id,
            site_id=site_id,
            occurred_at=occurred_at,
            source_type=source_type,
            source_id=row_id,
            recorded_by_user_id=uuid.UUID(cmd.created_by),
            idempotency_key=cmd.idempotency_key,
        )

        payload = {
            "material_name": cmd.material_name,
            "quantity": str(cmd.quantity),
            "unit": cmd.unit,
            "occurred_date": cmd.occurred_date.isoformat(),
            "occurred_date_source": cmd.occurred_date_source,
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
                "aggregate_type": aggregate_type,
                "aggregate_id": row_id,
                "event_type": event_type,
                "payload": json.dumps(payload),
                "correlation_id": cmd.correlation_id,
            },
        )

        result = ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=cmd.idempotency_key,
            material_row_id=str(row_id),
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
        self, conn: AsyncConnection, cmd: MaterialCommand, reasons: list[str]
    ) -> ExecutionResult:
        from sqlalchemy import text

        if not await self._try_claim(conn, cmd):
            existing = await self.check_idempotency(conn, cmd.idempotency_key)
            assert existing is not None
            return as_replay(existing)

        result = ExecutionResult(
            status=ExecutionStatus.REJECTED,
            idempotency_key=cmd.idempotency_key,
            rejection_reasons=reasons,
        )
        await conn.execute(
            text(
                "UPDATE idempotency_keys "
                "SET status = 'completed', result = CAST(:result AS jsonb), completed_at = now() "
                "WHERE key = :key"
            ),
            {"result": result.model_dump_json(), "key": cmd.idempotency_key},
        )

        await self._transition(conn, cmd.idempotency_key, WorkflowPhase.EXECUTION_REJECTED)
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
