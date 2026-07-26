"""Vendor existence check (wiring layer only).

Same shape and justification as runtime/duplicate_expense_query.py: adapts
the backend's PostgresVendorRepository.find_by_name_exact_active into a
plain async method the inbound journey can call before the graph runs (a
node must never query a repository itself -- see
workflows/expense_capture/nodes.py's `resolve_vendor` docstring). Never
opens a write transaction, never mutates state -- creating the vendor stays
the resolver's job (application/vendors/resolution.py), this only tells the
caller whether that create is about to happen so the user can be asked
first.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mesiri.infrastructure.postgres.database import PostgresDatabase


class VendorQueryService:
    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    async def exists(self, *, organization_id: str, vendor_name: str) -> bool:
        """True if an active vendor with this exact (case-insensitive) name
        already exists for the org. Mirrors the lookup
        application/vendors/resolution.py performs at record time, so a
        "yes" here and the resolver's own match agree."""
        from mesiri.infrastructure.postgres.repositories.vendors import PostgresVendorRepository

        org_id = uuid.UUID(organization_id)
        async with self._db.transaction() as conn:
            vendor = await PostgresVendorRepository(conn).find_by_name_exact_active(
                org_id, vendor_name
            )
        return vendor is not None
