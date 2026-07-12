"""Repository contracts for money accounts and money transactions."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Protocol

from .entities import MoneyAccount, MoneyTransaction


class MoneyAccountRepository(Protocol):
    async def get_by_id(
        self, organization_id: uuid.UUID, account_id: uuid.UUID
    ) -> MoneyAccount | None: ...

    async def get_balance(self, organization_id: uuid.UUID, account_id: uuid.UUID) -> Decimal:
        """opening_balance + sum(money_transactions in/out of this account)."""
        ...


class MoneyTransactionRepository(Protocol):
    async def record(
        self,
        *,
        organization_id: uuid.UUID,
        transaction_type: str,
        amount: Decimal,
        occurred_date: datetime.date,
        created_by: uuid.UUID,
        from_account_id: uuid.UUID | None = None,
        to_account_id: uuid.UUID | None = None,
        source_type: str | None = None,
        source_id: uuid.UUID | None = None,
        correlation_id: str | None = None,
    ) -> MoneyTransaction:
        """Confirmed financial history — insert-only, never mutated or hard-deleted."""
        ...

    async def reverse(
        self, organization_id: uuid.UUID, transaction_id: uuid.UUID, created_by: uuid.UUID
    ) -> MoneyTransaction:
        """Post the opposite-direction transaction; original row is untouched."""
        ...
