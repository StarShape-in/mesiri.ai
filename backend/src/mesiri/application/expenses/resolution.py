"""Resolve a RecordExpenseCommand's category_text against expense_categories.

Defense-in-depth guard, mirrors application/materials/resolution.py: by the
time a command reaches the Handler, `category_id` should already be set
(REST path) or resolvable from `category_text` (WhatsApp path, collected as
free text in conversation). No fuzzy matching or auto-create — an
unresolvable category is a rejection, not a guess.

`ExpenseCategoryResolver` is an injectable port so Handler unit tests can
supply a fake instead of hitting Postgres — see application/expenses/fakes.py.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mesiri.infrastructure.postgres.repositories.expenses import PostgresExpenseCategoryRepository

from .commands import RecordExpenseCommand

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    category_id: uuid.UUID | None
    reasons: list[str]


class ExpenseCategoryResolver(ABC):
    @abstractmethod
    async def resolve(self, conn: AsyncConnection, cmd: RecordExpenseCommand) -> ResolutionResult: ...


class PostgresExpenseCategoryResolver(ExpenseCategoryResolver):
    async def resolve(self, conn: AsyncConnection, cmd: RecordExpenseCommand) -> ResolutionResult:
        organization_id = uuid.UUID(cmd.organization_id)
        repo = PostgresExpenseCategoryRepository(conn)

        if cmd.category_id is not None:
            category = await repo.get_by_id(organization_id, uuid.UUID(cmd.category_id))
        else:
            category = await repo.find_by_name_exact_active(organization_id, cmd.category_text or "")

        if category is None or category.status != "active":
            label = cmd.category_text or cmd.category_id
            return ResolutionResult(category_id=None, reasons=[f"category '{label}' not found"])
        return ResolutionResult(category_id=category.id, reasons=[])
