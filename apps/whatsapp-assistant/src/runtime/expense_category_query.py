"""Expense category read service (wiring layer only).

Same shape and justification as runtime/material_catalog_query.py: adapts
the backend's PostgresExpenseCategoryRepository into a plain async method
the inbound journey can call to feed the org's real category names into the
extraction call (see understanding/pipeline.py's `expense_categories` param
and resolution.py's PostgresExpenseCategoryResolver, which this stays in
sync with -- the AI is nudged toward these same names, and the resolver
exact-matches against them as the safety net when the AI doesn't comply).

`list_active_category_names` lazily bootstraps a starter set of default
categories the first time an org has none (see
PostgresExpenseCategoryRepository.seed_defaults_if_empty), mirroring
runtime/money_account_query.py's default-account bootstrap -- callers must
never be handed an empty list for an org that simply hasn't set up
categories yet, since that would leave the AI nudging toward nothing and
every expense falling into "Uncategorized" until someone visits the
Categories page.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mesiri.infrastructure.postgres.database import PostgresDatabase


class ExpenseCategoryQueryService:
    """Reads active expense category names; only ever creates the org's
    default starter set, never mutates an existing category."""

    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    async def list_active_category_names(
        self, *, organization_id: str, created_by: str
    ) -> list[str]:
        from mesiri.infrastructure.postgres.repositories.expenses import (
            PostgresExpenseCategoryRepository,
        )

        async with self._db.transaction() as conn:
            repo = PostgresExpenseCategoryRepository(conn)
            categories = await repo.seed_defaults_if_empty(
                uuid.UUID(organization_id), created_by=uuid.UUID(created_by)
            )
            return [c.name for c in categories]
