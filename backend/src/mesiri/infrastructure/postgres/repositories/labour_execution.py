"""PostgreSQL implementation of mesiri.application.labour.repository.LabourExecutionRepository.

The only file permitted to hold SQL for labour_attendance_reports/_lines/
_attachments execution (capability-boundary convention, mirrors
material_execution.py). Every method takes an externally-supplied connection
— the Application Handler opens the one transaction (via
PostgresDatabase.transaction()); this repository never commits.

Reuses backend.postgres.workflow_instance's connection-scoped helpers
(transition_on_connection, get_by_id_on_connection) rather than duplicating
workflow_instances SQL here — that table's SQL stays owned by one file.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

from mesiri.application.labour.repository import LabourExecutionRepository
from mesiri.infrastructure.postgres.workflow_instance import (
    get_by_id_on_connection,
    transition_on_connection,
)
from mesiri_contracts.application.commands.labour import RecordLabourAttendanceCommand
from mesiri_contracts.application.results.execution_result import (
    ExecutionResult,
    ExecutionStatus,
    as_replay,
)
from mesiri_contracts.context.enums import WorkflowPhase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

_COMMAND_TYPE = "record_labour_attendance"


def _optional_uuid(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value is not None else None


class PostgresLabourExecutionRepository(LabourExecutionRepository):
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

    async def _try_claim(self, conn: AsyncConnection, cmd: RecordLabourAttendanceCommand) -> bool:
        """INSERT ... ON CONFLICT DO NOTHING — True if this call won the claim."""
        from sqlalchemy import text

        claimed = (
            await conn.execute(
                text(
                    "INSERT INTO idempotency_keys (key, command_type, status) "
                    "VALUES (:key, :command_type, 'in_progress') "
                    "ON CONFLICT (key) DO NOTHING RETURNING key"
                ),
                {"key": cmd.idempotency_key, "command_type": _COMMAND_TYPE},
            )
        ).first()
        return claimed is not None

    async def _ensure_worker_identities(
        self,
        conn: AsyncConnection,
        cmd: RecordLabourAttendanceCommand,
        organization_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> dict[int, uuid.UUID]:
        """Give every named worker a durable id, creating one if they are new.

        Returns {line index -> worker_id} for the lines that arrived without
        one. Headcount groups are skipped: "7 masons" names nobody, so there is
        no identity to assign and worker_id stays NULL for them.

        **This deliberately departs from the Labour plan's principle P1**
        ("attendance never writes the register"). P1 existed to stop the
        register filling with one-off names, but the cost turned out to be
        worse: a temporary worker had no id at all, so their history was keyed
        on the *name string*, and promoting them later started a second,
        separate history under a real id. Production shows the result -- 26
        people in attendance, only 8 of them linked to a register row, and the
        rest with histories that cannot survive being promoted.

        The register still distinguishes them: a worker created here is
        ``worker_type='temporary'``, and promotion flips that to
        ``'permanent'`` on the *same row*, so the id -- and every day of
        attendance already attached to it -- carries straight through.

        Find-or-create is keyed on normalized name + normalized trade, the same
        rule matching itself uses, so this can only ever create someone
        matching had already decided was nobody it knew. Doing it inside the
        report's own transaction is what makes it safe: two reports naming the
        same new person cannot race into two rows.
        """
        from sqlalchemy import text

        from mesiri.domains.workforce.workers import normalize_name, normalize_trade

        wanted: dict[int, tuple[str, str | None]] = {}
        for index, line in enumerate(cmd.lines):
            if _optional_uuid(line.worker_id) is not None:
                continue
            normalized = normalize_name(line.worker_name)
            if not normalized:
                continue
            wanted[index] = (normalized, normalize_trade(line.trade))
        if not wanted:
            return {}

        existing = (
            await conn.execute(
                text(
                    "SELECT id, name, trade FROM workforce_workers "
                    "WHERE organization_id = :org_id"
                ),
                {"org_id": organization_id},
            )
        ).mappings().all()
        by_key: dict[tuple[str, str | None], uuid.UUID] = {}
        for row in existing:
            by_key.setdefault(
                (normalize_name(row["name"]), normalize_trade(row["trade"])), row["id"]
            )

        resolved: dict[int, uuid.UUID] = {}
        for index, key in wanted.items():
            found = by_key.get(key)
            if found is None:
                found = uuid.uuid4()
                await conn.execute(
                    text(
                        "INSERT INTO workforce_workers "
                        "(id, organization_id, name, trade, worker_type, default_daily_wage, "
                        " contractor, status, created_at, created_by, updated_at) "
                        "VALUES (:id, :org_id, :name, :trade, 'temporary', :daily_wage, "
                        "        :contractor, 'active', now(), :created_by, now())"
                    ),
                    {
                        "id": found,
                        "org_id": organization_id,
                        # Stored as reported, not normalized -- normalization is
                        # a matching aid and was never meant for display.
                        "name": cmd.lines[index].worker_name,
                        "trade": cmd.lines[index].trade,
                        "daily_wage": cmd.lines[index].daily_wage,
                        "contractor": cmd.lines[index].contractor,
                        "created_by": created_by,
                    },
                )
                # Registered immediately so a second line naming the same
                # person in this very report reuses the row instead of
                # creating a twin.
                by_key[key] = found
            resolved[index] = found
        return resolved

    async def persist_success(
        self, conn: AsyncConnection, cmd: RecordLabourAttendanceCommand
    ) -> ExecutionResult:
        from sqlalchemy import text

        if not await self._try_claim(conn, cmd):
            # A concurrent transaction already claimed this key -- see
            # material_execution.py's identical comment for why this is
            # ALREADY_EXECUTED rather than SUCCEEDED.
            existing = await self.check_idempotency(conn, cmd.idempotency_key)
            assert existing is not None
            return as_replay(existing)

        organization_id = uuid.UUID(cmd.organization_id)
        project_id = _optional_uuid(cmd.project_id)
        site_id = _optional_uuid(cmd.site_id)
        created_by = uuid.UUID(cmd.created_by)

        if project_id is None:
            # domains/workforce/validation.py already rejects this before
            # persist_success is ever called; this is a defensive guard
            # against calling this method directly with an unvalidated
            # command, matching material_execution.py's equivalent check.
            raise RuntimeError("project_id is required to persist a labour attendance report")

        report_id = uuid.uuid4()
        await conn.execute(
            text(
                "INSERT INTO labour_attendance_reports "
                "(id, organization_id, project_id, site_id, occurred_date, recorded_via, "
                "notes, correlation_id, corrects_report_id, created_by) "
                "VALUES (:id, :organization_id, :project_id, :site_id, :occurred_date, "
                ":recorded_via, :notes, :correlation_id, :corrects_report_id, :created_by)"
            ),
            {
                "id": report_id,
                "organization_id": organization_id,
                "project_id": project_id,
                "site_id": site_id,
                "occurred_date": cmd.occurred_date,
                "recorded_via": cmd.recorded_via,
                "notes": cmd.notes,
                "correlation_id": cmd.correlation_id,
                # Reserved by migration 0371 and, until now, written by
                # nothing -- so the read side's supersede rule (which every
                # total already applies) could never actually fire. This is
                # the writer it was waiting for.
                "corrects_report_id": _optional_uuid(cmd.corrects_report_id),
                "created_by": created_by,
            },
        )

        identities = await self._ensure_worker_identities(conn, cmd, organization_id, created_by)

        for index, line in enumerate(cmd.lines):
            await conn.execute(
                text(
                    "INSERT INTO labour_attendance_lines "
                    "(id, report_id, worker_id, worker_name, worker_name_original, trade, "
                    "headcount, daily_wage, contractor, activity, created_at) "
                    "VALUES (:id, :report_id, :worker_id, :worker_name, :worker_name_original, "
                    ":trade, :headcount, :daily_wage, :contractor, :activity, now())"
                ),
                {
                    "id": uuid.uuid4(),
                    "report_id": report_id,
                    "worker_id": _optional_uuid(line.worker_id) or identities.get(index),
                    "worker_name": line.worker_name,
                    "worker_name_original": line.worker_name_original,
                    "trade": line.trade,
                    "headcount": line.headcount,
                    "daily_wage": line.daily_wage,
                    "contractor": line.contractor,
                    "activity": line.activity,
                },
            )

        for object_key in cmd.attachment_object_keys:
            await conn.execute(
                text(
                    "INSERT INTO labour_attendance_attachments "
                    "(id, report_id, media_object_key, attachment_type, created_at, created_by) "
                    "VALUES (:id, :report_id, :media_object_key, 'attendance_sheet', now(), :created_by)"
                ),
                {
                    "id": uuid.uuid4(),
                    "report_id": report_id,
                    "media_object_key": object_key,
                    "created_by": created_by,
                },
            )

        # Generic outbox row, same mechanism material_receipts/material_usage
        # already write to -- this is what a future Timeline consumer reads
        # from (Labour plan principle P8: store the facts now, build the
        # consumer later). No Labour-specific event infrastructure needed.
        payload = {
            "occurred_date": cmd.occurred_date.isoformat(),
            "occurred_date_source": cmd.occurred_date_source,
            "recorded_via": cmd.recorded_via,
            "total_headcount": cmd.total_headcount,
            "total_cost": str(cmd.total_cost),
            "line_count": len(cmd.lines),
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
                "aggregate_type": "labour_attendance_report",
                "aggregate_id": report_id,
                "event_type": "LabourAttendanceRecorded",
                "payload": json.dumps(payload),
                "correlation_id": cmd.correlation_id,
            },
        )

        result = ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=cmd.idempotency_key,
            # Shared contract field, named for materials since that module
            # shipped first (see channel/receipt/data.py's RecordReceiptBuilder
            # docstring) -- every module's row id travels through it. Here it
            # is the Attendance ID: labour_attendance_reports.id.
            material_row_id=str(report_id),
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
        self, conn: AsyncConnection, cmd: RecordLabourAttendanceCommand, reasons: list[str]
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
