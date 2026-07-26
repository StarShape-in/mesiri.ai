"""Reversal target read service (wiring layer only).

Same shape and justification as runtime/money_account_query.py: adapts the
backend's PostgresExpenseRepository.find_latest_confirmed /
PostgresMoneyTransactionRepository.find_latest_reversible_transfer into
plain async methods the inbound journey can call before the graph runs (a
node must never query a repository itself -- see workflows/reverse/nodes.py's
docstring). Never opens a write transaction, never mutates state -- Finance
Module Slice 7's "reverse" itself only ever happens after confirmation, via
application/finance/reverse_execution.py.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from mesiri.infrastructure.postgres.database import PostgresDatabase


class ReversalExpenseTarget(TypedDict):
    expense_id: str
    amount: str
    description: str | None
    occurred_date: str


class ReversalTransferTarget(TypedDict):
    money_transaction_id: str
    amount: str
    from_account_name: str
    to_account_name: str


class ReversalTargetQueryService:
    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    async def find_latest_expense(
        self, *, organization_id: str, project_id: str | None, site_id: str | None
    ) -> ReversalExpenseTarget | None:
        from mesiri.infrastructure.postgres.repositories.expenses import PostgresExpenseRepository

        async with self._db.transaction() as conn:
            repo = PostgresExpenseRepository(conn)
            expense = await repo.find_latest_confirmed(
                uuid.UUID(organization_id),
                project_id=uuid.UUID(project_id) if project_id else None,
                site_id=uuid.UUID(site_id) if site_id else None,
            )
        if expense is None:
            return None
        return ReversalExpenseTarget(
            expense_id=str(expense.id),
            amount=str(expense.amount),
            description=expense.description,
            occurred_date=expense.occurred_date.isoformat(),
        )

    async def find_latest_transfer(self, *, organization_id: str) -> ReversalTransferTarget | None:
        from mesiri.infrastructure.postgres.repositories.finance import (
            PostgresMoneyAccountRepository,
            PostgresMoneyTransactionRepository,
        )

        org_id = uuid.UUID(organization_id)
        async with self._db.transaction() as conn:
            transactions = PostgresMoneyTransactionRepository(conn)
            transaction = await transactions.find_latest_reversible_transfer(org_id)
            if transaction is None:
                return None
            accounts = PostgresMoneyAccountRepository(conn)
            from_account = (
                await accounts.get_by_id(org_id, transaction.from_account_id)
                if transaction.from_account_id
                else None
            )
            to_account = (
                await accounts.get_by_id(org_id, transaction.to_account_id)
                if transaction.to_account_id
                else None
            )
        return ReversalTransferTarget(
            money_transaction_id=str(transaction.id),
            amount=str(Decimal(transaction.amount)),
            from_account_name=from_account.name if from_account else "unknown account",
            to_account_name=to_account.name if to_account else "unknown account",
        )
