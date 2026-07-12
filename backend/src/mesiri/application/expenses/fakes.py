"""In-memory ExpenseExecutionRepository/ExpenseCategoryResolver for tests.

Mirrors mesiri.application.materials.fakes' style.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

from mesiri_contracts.application.results.execution_result import (
    ExecutionResult,
    ExecutionStatus,
    as_replay,
)
from mesiri_contracts.context.enums import WorkflowPhase

from .commands import RecordExpenseCommand
from .repository import ExpenseExecutionRepository
from .resolution import ExpenseCategoryResolver, ResolutionResult


class FakeDatabase:
    """Duck-typed stand-in for PostgresDatabase — no engine, no SQL.

    `.transaction()` yields None; the fake repository used alongside it
    ignores the `conn` argument entirely, so no real connection is needed
    for handle_confirmed() unit tests. Mirrors
    mesiri.application.materials.fakes.FakeDatabase.
    """

    @asynccontextmanager
    async def transaction(self):
        yield None


class FakeExpenseExecutionRepository(ExpenseExecutionRepository):
    """Optionally wraps a workflows.fakes.FakeWorkflowInstanceRepository so
    tests can observe the workflow phase transition (COMPLETED/
    EXECUTION_REJECTED) the same way PostgresExpenseExecutionRepository
    performs it atomically alongside the domain write. Mirrors
    mesiri.application.materials.fakes.FakeMaterialExecutionRepository.
    """

    def __init__(self, workflow_repo: Any | None = None) -> None:
        # idempotency_key -> ExecutionResult, mirrors idempotency_keys.result
        self._claims: dict[str, ExecutionResult] = {}
        # expense rows actually "persisted", for test assertions
        self.expense_rows: list[dict[str, Any]] = []
        self._workflow_repo = workflow_repo

    async def check_idempotency(self, conn: Any, key: str) -> ExecutionResult | None:
        return self._claims.get(key)

    async def persist_success(self, conn: Any, cmd: RecordExpenseCommand) -> ExecutionResult:
        if cmd.idempotency_key in self._claims:
            return as_replay(self._claims[cmd.idempotency_key])

        expense_id = str(uuid.uuid4())
        self.expense_rows.append({"id": expense_id, "command": cmd})
        result = ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=cmd.idempotency_key,
            material_row_id=expense_id,
        )
        self._claims[cmd.idempotency_key] = result
        await self._transition(cmd.idempotency_key, WorkflowPhase.COMPLETED)
        return result

    async def persist_rejection(
        self, conn: Any, cmd: RecordExpenseCommand, reasons: list[str]
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


class PersistSuccessRaisesRepository(ExpenseExecutionRepository):
    """persist_success raises; persist_rejection behaves normally — proves the
    Handler never calls persist_success for a command it already knows is invalid."""

    async def check_idempotency(self, conn: Any, key: str) -> ExecutionResult | None:
        return None

    async def persist_success(self, conn: Any, cmd: RecordExpenseCommand) -> ExecutionResult:
        raise AssertionError("persist_success must not be called for an invalid command")

    async def persist_rejection(
        self, conn: Any, cmd: RecordExpenseCommand, reasons: list[str]
    ) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.REJECTED,
            idempotency_key=cmd.idempotency_key,
            rejection_reasons=reasons,
        )


class FakeExpenseCategoryResolver(ExpenseCategoryResolver):
    """Always resolves successfully to a deterministic category_id derived
    from cmd.category_text, so different names in the same test get
    different (but stable) ids. No catalog/DB involved."""

    async def resolve(self, conn: Any, cmd: RecordExpenseCommand) -> ResolutionResult:
        category_id = uuid.uuid5(
            uuid.NAMESPACE_DNS, f"expense_category:{(cmd.category_text or '').strip().lower()}"
        )
        return ResolutionResult(category_id=category_id, reasons=[])


class RejectingExpenseCategoryResolver(ExpenseCategoryResolver):
    """Always rejects with the given reasons — for testing the resolution-failure path."""

    def __init__(self, reasons: list[str]) -> None:
        self._reasons = reasons

    async def resolve(self, conn: Any, cmd: RecordExpenseCommand) -> ResolutionResult:
        return ResolutionResult(category_id=None, reasons=self._reasons)
