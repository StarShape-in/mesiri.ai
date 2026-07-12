"""In-memory MaterialExecutionRepository for tests — no DB, no SQL.

Mirrors workflows.fakes.FakeWorkflowInstanceRepository's style. Optionally
wraps a FakeWorkflowInstanceRepository so tests can observe the workflow
phase transition (COMPLETED/EXECUTION_REJECTED) the same way the real
Postgres repository performs it atomically alongside the domain write.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

from mesiri_contracts.application.commands.material import RecordMaterialReceiptCommand
from mesiri_contracts.application.results.execution_result import (
    ExecutionResult,
    ExecutionStatus,
    as_replay,
)
from mesiri_contracts.context.enums import WorkflowPhase

from .repository import MaterialCommand, MaterialExecutionRepository
from .resolution import MaterialResolver, ResolutionResult


class FakeDatabase:
    """Duck-typed stand-in for PostgresDatabase — no engine, no SQL.

    `.transaction()` yields None; the fake repositories used alongside it
    ignore the `conn` argument entirely, so no real connection is needed for
    Handler-level unit tests.
    """

    @asynccontextmanager
    async def transaction(self):
        yield None


class FakeMaterialExecutionRepository(MaterialExecutionRepository):
    def __init__(self, workflow_repo: Any | None = None) -> None:
        # idempotency_key -> ExecutionResult, mirrors idempotency_keys.result
        self._claims: dict[str, ExecutionResult] = {}
        # material rows actually "persisted", for test assertions
        self.material_rows: list[dict[str, Any]] = []
        # optional workflows.fakes.FakeWorkflowInstanceRepository, to simulate
        # the atomic phase transition the real repository performs
        self._workflow_repo = workflow_repo

    async def check_idempotency(self, conn: Any, key: str) -> ExecutionResult | None:
        return self._claims.get(key)

    async def persist_success(self, conn: Any, cmd: MaterialCommand) -> ExecutionResult:
        if cmd.idempotency_key in self._claims:
            return as_replay(self._claims[cmd.idempotency_key])

        row_id = str(uuid.uuid4())
        self.material_rows.append(
            {
                "id": row_id,
                "table": "material_receipts"
                if isinstance(cmd, RecordMaterialReceiptCommand)
                else "material_usage",
                "command": cmd,
            }
        )
        result = ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=cmd.idempotency_key,
            material_row_id=row_id,
        )
        self._claims[cmd.idempotency_key] = result
        await self._transition(cmd.idempotency_key, WorkflowPhase.COMPLETED)
        return result

    async def persist_rejection(
        self, conn: Any, cmd: MaterialCommand, reasons: list[str]
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


class FakeMaterialResolver(MaterialResolver):
    """Always resolves successfully to a deterministic (material_id, unit_id) pair,
    derived from cmd.material_name/unit so different names/units in the same test
    get different (but stable) ids. No catalog/DB involved."""

    async def resolve(self, conn: Any, cmd: MaterialCommand) -> ResolutionResult:
        material_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"material:{cmd.material_name.strip().lower()}")
        unit_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"unit:{cmd.unit.strip().lower()}")
        return ResolutionResult(material_id=material_id, unit_id=unit_id, reasons=[])


class RejectingMaterialResolver(MaterialResolver):
    """Always rejects with the given reasons — for testing the resolution-failure path."""

    def __init__(self, reasons: list[str]) -> None:
        self._reasons = reasons

    async def resolve(self, conn: Any, cmd: MaterialCommand) -> ResolutionResult:
        return ResolutionResult(material_id=None, unit_id=None, reasons=self._reasons)


class PersistSuccessRaisesRepository(MaterialExecutionRepository):
    """persist_success raises; persist_rejection behaves normally.

    Proves the Handler decides validity itself (via the pure validate() call,
    before any transaction/repo interaction) and dispatches to the correct
    repo method — the repository is never asked to persist a success for a
    command the Handler already knows is invalid, and never re-validates
    internally. Used with a deliberately-invalid command: if the ordering
    were wrong (e.g. the repo re-validating and persisting anyway), this
    would raise; instead persist_rejection runs and returns REJECTED cleanly.
    """

    async def check_idempotency(self, conn: Any, key: str) -> ExecutionResult | None:
        return None

    async def persist_success(self, conn: Any, cmd: MaterialCommand) -> ExecutionResult:
        raise AssertionError("persist_success must not be called for an invalid command")

    async def persist_rejection(
        self, conn: Any, cmd: MaterialCommand, reasons: list[str]
    ) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.REJECTED,
            idempotency_key=cmd.idempotency_key,
            rejection_reasons=reasons,
        )
