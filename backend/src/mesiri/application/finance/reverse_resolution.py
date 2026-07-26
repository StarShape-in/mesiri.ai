"""Defense-in-depth check that the reversal target is still reversible.

runtime/inbound_journey.py's seeding step already found "the most recent
expense/transfer" at draft-build time (see workflows/reverse/nodes.py), so
this never resolves a name or a fuzzy reference -- it only re-verifies the
target still exists and hasn't already been reversed/voided at confirm
time, since time can pass between the draft being built and the user
replying YES (mirrors application/finance/transfer_resolution.py's
re-verify-at-confirm-time reasoning).
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mesiri.infrastructure.postgres.repositories.expenses import PostgresExpenseRepository
from mesiri.infrastructure.postgres.repositories.finance import PostgresMoneyTransactionRepository

from .reverse_commands import ReverseTransactionCommand

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    reasons: list[str]


class ReverseTargetResolver(ABC):
    @abstractmethod
    async def resolve(
        self, conn: AsyncConnection, cmd: ReverseTransactionCommand
    ) -> ResolutionResult: ...


class PostgresReverseTargetResolver(ReverseTargetResolver):
    async def resolve(
        self, conn: AsyncConnection, cmd: ReverseTransactionCommand
    ) -> ResolutionResult:
        organization_id = uuid.UUID(cmd.organization_id)

        if cmd.target_kind == "expense":
            assert cmd.expense_id is not None
            expenses = PostgresExpenseRepository(conn)
            expense = await expenses.get_by_id(organization_id, uuid.UUID(cmd.expense_id))
            if expense is None:
                return ResolutionResult(reasons=["that expense no longer exists"])
            if expense.workflow_status != "confirmed":
                return ResolutionResult(
                    reasons=[f"that expense is already {expense.workflow_status}"]
                )
            return ResolutionResult(reasons=[])

        assert cmd.money_transaction_id is not None
        transactions = PostgresMoneyTransactionRepository(conn)
        transaction_id = uuid.UUID(cmd.money_transaction_id)
        transaction = await transactions.get_by_id(organization_id, transaction_id)
        if transaction is None:
            return ResolutionResult(reasons=["that transfer no longer exists"])
        if transaction.transaction_type != "transfer":
            return ResolutionResult(reasons=["that transaction is not a transfer"])
        if await transactions.is_reversed(organization_id, transaction_id):
            return ResolutionResult(reasons=["that transfer has already been reversed"])
        return ResolutionResult(reasons=[])
