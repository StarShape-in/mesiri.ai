"""Vendor name resolution (wiring layer only).

Same shape and justification as runtime/duplicate_expense_query.py: adapts
the backend's PostgresVendorRepository into plain async methods the inbound
journey can call before the graph runs (a node must never query a repository
itself -- see workflows/expense_capture/nodes.py's `resolve_vendor`
docstring). Never opens a write transaction, never mutates state -- creating
the vendor stays the resolver's job (application/vendors/resolution.py),
this only tells the caller what that create is about to do so the user can
be asked first.

Phase 4 (ENTITY_RESOLUTION_PLAN.md §5) replaced the original exact-match
`exists()` with `resolve()`, on the shared Resolved/Ambiguous/Missing
vocabulary, because exact-match-only was quietly producing duplicate vendor
rows: `application/vendors/resolution.py` creates a brand-new vendor for any
`vendor_text` its own exact match misses, so reporting "Sharma Traders" when
the org already had "Sharma Trading Co" answered "I don't have that vendor
yet -- add it?" and, on Yes, wrote a second row for the same business. That
is the §1 Hysam bug with a vendor instead of a person, and it compounds:
each near-miss spelling becomes another row, and spend splits across them.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from runtime.entity_resolution.name_matching import NamedCandidate, resolve_name_hint
from workflows.entities import ResolutionOutcome

if TYPE_CHECKING:
    from mesiri.infrastructure.postgres.database import PostgresDatabase


class VendorQueryService:
    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    async def resolve(self, *, organization_id: str, vendor_name: str) -> ResolutionOutcome:
        """Score the reported vendor name against the org's active vendors.

        Person-like matching (difflib, via name_matching) rather than the
        catalog-like SQL substring materials use: a business name a site
        engineer types is a free-hand rendering of a name they heard, so
        "Sharma Traders"/"Sharma Trading Co" must meet, and substring would
        never connect them (neither contains the other).
        """
        candidates = await self._list_active(organization_id)
        return resolve_name_hint(vendor_name, candidates)

    async def _list_active(self, organization_id: str) -> list[NamedCandidate]:
        from mesiri.infrastructure.postgres.repositories.vendors import PostgresVendorRepository

        org_id = uuid.UUID(organization_id)
        async with self._db.transaction() as conn:
            vendors = await PostgresVendorRepository(conn).list_active(org_id)
        return [NamedCandidate(entity_id=str(v.id), display_name=v.name) for v in vendors]
