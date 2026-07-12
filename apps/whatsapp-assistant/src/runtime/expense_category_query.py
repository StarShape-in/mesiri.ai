"""Expense category read service (wiring layer only).

Same shape and justification as runtime/material_catalog_query.py: adapts
the backend's PostgresExpenseCategoryRepository into a plain async method
the inbound journey can call to feed the org's real category names into the
extraction call (see understanding/pipeline.py's `expense_categories` param
and resolution.py's PostgresExpenseCategoryResolver, which this stays in
sync with -- the AI is nudged toward these same names, and the resolver
exact-matches against them as the safety net when the AI doesn't comply).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mesiri.infrastructure.postgres.database import PostgresDatabase


class ExpenseCategoryQueryService:
    """Read-only: never opens a write transaction, never mutates state."""

    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    async def list_active_category_names(self, *, organization_id: str) -> list[str]:
        from mesiri.infrastructure.postgres.repositories.expenses import (
            PostgresExpenseCategoryRepository,
        )

        async with self._db.transaction() as conn:
            repo = PostgresExpenseCategoryRepository(conn)
            categories = await repo.list_active(uuid.UUID(organization_id))
            return [c.name for c in categories]
