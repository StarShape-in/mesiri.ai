"""Repository contracts for expenses, categories, attachments, payments, budgets."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Protocol

from .entities import (
    Expense,
    ExpenseAttachment,
    ExpenseCategory,
    ExpensePayment,
)


class ExpenseCategoryRepository(Protocol):
    async def list_active(self, organization_id: uuid.UUID) -> list[ExpenseCategory]: ...

    async def get_by_id(
        self, organization_id: uuid.UUID, category_id: uuid.UUID
    ) -> ExpenseCategory | None: ...


class ExpenseRepository(Protocol):
    async def get_by_id(
        self, organization_id: uuid.UUID, expense_id: uuid.UUID
    ) -> Expense | None: ...


class ExpenseAttachmentRepository(Protocol):
    async def list_for_expense(
        self, organization_id: uuid.UUID, expense_id: uuid.UUID
    ) -> list[ExpenseAttachment]: ...


class ExpensePaymentRepository(Protocol):
    async def list_for_expense(
        self, organization_id: uuid.UUID, expense_id: uuid.UUID
    ) -> list[ExpensePayment]: ...

    async def record_payment(
        self,
        *,
        organization_id: uuid.UUID,
        expense_id: uuid.UUID,
        account_id: uuid.UUID,
        amount: Decimal,
        paid_date: datetime.date,
        created_by: uuid.UUID,
    ) -> ExpensePayment:
        """Atomically creates the payment row and its money_transactions
        counterpart; rejects if it would push confirmed payments over the
        expense amount."""
        ...

    async def reverse_payment(
        self, organization_id: uuid.UUID, payment_id: uuid.UUID, created_by: uuid.UUID
    ) -> ExpensePayment:
        """Marks the payment reversed and posts a reversal money_transaction;
        never deletes the original payment or transaction."""
        ...


class BudgetRepository(Protocol):
    async def get_actual_spend(
        self, organization_id: uuid.UUID, budget_id: uuid.UUID
    ) -> Decimal:
        """Sum of confirmed, non-voided expenses within the budget's project
        (and category, for category-level allocations)."""
        ...
