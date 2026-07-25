"""Petty cash recipient read/bootstrap service (wiring layer only).

Same shape and justification as runtime/money_account_query.py: adapts the
backend's PostgresPettyCashRecipientResolver into a plain async method the
inbound journey can call before the graph runs (a node must never query a
repository itself -- see workflows/petty_cash/nodes.py's docstring).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mesiri.domains.finance.entities import MoneyAccount
    from mesiri.infrastructure.postgres.database import PostgresDatabase


class PettyCashRecipientQueryService:
    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    async def resolve_or_create_advance_account(
        self, *, organization_id: str, recipient_name: str, created_by: str
    ) -> MoneyAccount | None:
        from mesiri.application.finance.petty_cash_resolution import (
            PostgresPettyCashRecipientResolver,
        )

        resolver = PostgresPettyCashRecipientResolver()
        async with self._db.transaction() as conn:
            return await resolver.resolve_or_create_advance_account(
                conn,
                uuid.UUID(organization_id),
                recipient_name,
                created_by=uuid.UUID(created_by),
            )
