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
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from mesiri.infrastructure.postgres.database import PostgresDatabase

_CATEGORY_CACHE_TTL = 300  # 5 minutes


class _RedisLike(Protocol):
    def namespaced(self, *parts: str) -> str: ...
    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None: ...
    async def get_json(self, key: str) -> Any | None: ...


class ExpenseCategoryQueryService:
    """Reads active expense category names; only ever creates the org's
    default starter set, never mutates an existing category.

    When ``redis`` is supplied the category list is cached per-org for
    ``_CATEGORY_CACHE_TTL`` seconds (5 min). Category lists change rarely;
    a short TTL is safe and eliminates Postgres round-trips for the vast
    majority of messages.
    """

    def __init__(self, db: PostgresDatabase, redis: _RedisLike | None = None) -> None:
        self._db = db
        self._redis = redis

    async def list_active_category_names(
        self, *, organization_id: str, created_by: str
    ) -> list[str]:
        # --- Cache read ---
        cache_key: str | None = None
        if self._redis is not None:
            cache_key = self._redis.namespaced("expense_categories", organization_id)
            cached = await self._redis.get_json(cache_key)
            if isinstance(cached, list):
                return cached

        # --- Postgres read ---
        from mesiri.infrastructure.postgres.repositories.expenses import (
            PostgresExpenseCategoryRepository,
        )

        async with self._db.transaction() as conn:
            repo = PostgresExpenseCategoryRepository(conn)
            categories = await repo.seed_defaults_if_empty(
                uuid.UUID(organization_id), created_by=uuid.UUID(created_by)
            )
        names = [c.name for c in categories]

        # --- Cache write ---
        if self._redis is not None and cache_key is not None:
            await self._redis.set_json(cache_key, names, ttl_seconds=_CATEGORY_CACHE_TTL)

        return names
