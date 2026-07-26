"""In-memory LabourExecutionRepository for tests — no DB, no SQL.

Mirrors application/materials/fakes.py's style exactly. Optionally wraps a
FakeWorkflowInstanceRepository so tests can observe the workflow phase
transition (COMPLETED/EXECUTION_REJECTED) the same way the real Postgres
repository performs it atomically alongside the domain write.

No fake resolver here, unlike materials/fakes.py -- Labour has no equivalent
resolution step (see repository.py's docstring: worker matching already
happened in the workflow before confirmation).
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

from mesiri_contracts.application.commands.labour import RecordLabourAttendanceCommand
from mesiri_contracts.application.results.execution_result import (
    ExecutionResult,
    ExecutionStatus,
    as_replay,
)
from mesiri_contracts.context.enums import WorkflowPhase

from .repository import LabourExecutionRepository


class FakeDatabase:
    """Duck-typed stand-in for PostgresDatabase — no engine, no SQL.

    `.transaction()` yields None; the fake repository used alongside it
    ignores the `conn` argument entirely, so no real connection is needed for
    Handler-level unit tests.
    """

    @asynccontextmanager
    async def transaction(self):
        yield None


class FakeLabourExecutionRepository(LabourExecutionRepository):
    def __init__(self, workflow_repo: Any | None = None) -> None:
        # idempotency_key -> ExecutionResult, mirrors idempotency_keys.result
        self._claims: dict[str, ExecutionResult] = {}
        # attendance reports actually "persisted", for test assertions --
        # each entry carries the command so a test can inspect every line
        # and attachment without a real database.
        self.reports: list[dict[str, Any]] = []
        # optional workflows.fakes.FakeWorkflowInstanceRepository, to simulate
        # the atomic phase transition the real repository performs
        self._workflow_repo = workflow_repo

    async def check_idempotency(self, conn: Any, key: str) -> ExecutionResult | None:
        return self._claims.get(key)

    async def persist_success(
        self, conn: Any, cmd: RecordLabourAttendanceCommand
    ) -> ExecutionResult:
        if cmd.idempotency_key in self._claims:
            return as_replay(self._claims[cmd.idempotency_key])

        report_id = str(uuid.uuid4())
        self.reports.append({"id": report_id, "command": cmd})
        result = ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=cmd.idempotency_key,
            material_row_id=report_id,
        )
        self._claims[cmd.idempotency_key] = result
        await self._transition(cmd.idempotency_key, WorkflowPhase.COMPLETED)
        return result

    async def persist_rejection(
        self, conn: Any, cmd: RecordLabourAttendanceCommand, reasons: list[str]
    ) -> ExecutionResult:
        if cmd.idempotency_key in self._claims:
            return as_replay(self._claims[cmd.idempotency_key])

        result = ExecutionResult(
            status=ExecutionStatus.REJECTED,
            idempotency_key=cmd.idempotency_key,
            rejection_reasons=reasons,
        )
        self._claims[cmd.idempotency_key] = result
        await self._transition(cmd.idempotency_key, WorkflowPhase.EXECUTION_REJECTED)
        return result

    async def _transition(self, workflow_instance_id: str, new_phase: WorkflowPhase) -> None:
        if self._workflow_repo is None:
            return
        row = self._workflow_repo._rows.get(workflow_instance_id)  # noqa: SLF001 — test fake
        if row is None:
            return
        state, version = row
        new_state = state.model_copy(update={"phase": new_phase})
        await self._workflow_repo.transition(workflow_instance_id, version, new_state)


class PersistSuccessRaisesRepository(LabourExecutionRepository):
    """persist_success raises; persist_rejection behaves normally.

    Mirrors materials/fakes.py's identical fixture. Proves the Handler
    decides validity itself (via the pure validate() call, before any
    transaction/repo interaction) — the repository is never asked to persist
    a success for a command the Handler already knows is invalid.
    """

    async def check_idempotency(self, conn: Any, key: str) -> ExecutionResult | None:
        return None

    async def persist_success(
        self, conn: Any, cmd: RecordLabourAttendanceCommand
    ) -> ExecutionResult:
        raise AssertionError("persist_success must not be called for an invalid command")

    async def persist_rejection(
        self, conn: Any, cmd: RecordLabourAttendanceCommand, reasons: list[str]
    ) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.REJECTED,
            idempotency_key=cmd.idempotency_key,
            rejection_reasons=reasons,
        )
