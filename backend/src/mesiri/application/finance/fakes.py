"""In-memory AccountAdminExecutionRepository/AccountLookupResolver for tests.

Mirrors application/expenses/fakes' style.
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

from .commands import ManageMoneyAccountCommand
from .repository import AccountAdminExecutionRepository
from .resolution import AccountLookupResolver, ResolutionResult


class FakeDatabase:
    """Duck-typed stand-in for PostgresDatabase — no engine, no SQL. Mirrors
    mesiri.application.expenses.fakes.FakeDatabase."""

    @asynccontextmanager
    async def transaction(self):
        yield None


class FakeAccountAdminExecutionRepository(AccountAdminExecutionRepository):
    def __init__(self) -> None:
        # idempotency_key -> ExecutionResult, mirrors idempotency_keys.result
        self._claims: dict[str, ExecutionResult] = {}
        # accounts actually "written", for test assertions
        self.account_writes: list[dict[str, Any]] = []

    async def check_idempotency(self, conn: Any, key: str) -> ExecutionResult | None:
        return self._claims.get(key)

    async def persist_success(self, conn: Any, cmd: ManageMoneyAccountCommand) -> ExecutionResult:
        if cmd.idempotency_key in self._claims:
            return as_replay(self._claims[cmd.idempotency_key])

        row_id = cmd.target_account_id or str(uuid.uuid4())
        self.account_writes.append({"id": row_id, "command": cmd})
        result = ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=cmd.idempotency_key,
            material_row_id=row_id,
        )
        self._claims[cmd.idempotency_key] = result
        return result

    async def persist_rejection(
        self, conn: Any, cmd: ManageMoneyAccountCommand, reasons: list[str]
    ) -> ExecutionResult:
        if cmd.idempotency_key in self._claims:
            return as_replay(self._claims[cmd.idempotency_key])

        result = ExecutionResult(
            status=ExecutionStatus.REJECTED,
            idempotency_key=cmd.idempotency_key,
            rejection_reasons=reasons,
        )
        self._claims[cmd.idempotency_key] = result
        return result


class FakeAccountLookupResolver(AccountLookupResolver):
    """Deterministic: `create` never collides, `rename`/`deactivate` always
    resolve to a stable id derived from target_name. No catalog/DB involved."""

    async def resolve(self, conn: Any, cmd: ManageMoneyAccountCommand) -> ResolutionResult:
        if cmd.action == "create":
            return ResolutionResult(target_account_id=None, reasons=[])
        target_account_id = uuid.uuid5(
            uuid.NAMESPACE_DNS, f"money_account:{(cmd.target_name or '').strip().lower()}"
        )
        return ResolutionResult(target_account_id=target_account_id, reasons=[])


class RejectingAccountLookupResolver(AccountLookupResolver):
    """Always rejects with the given reasons — for testing the resolution-failure path."""

    def __init__(self, reasons: list[str]) -> None:
        self._reasons = reasons

    async def resolve(self, conn: Any, cmd: ManageMoneyAccountCommand) -> ResolutionResult:
        return ResolutionResult(target_account_id=None, reasons=self._reasons)
