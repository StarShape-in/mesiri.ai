"""Resolve a project-member name hint ("Hysam") against an org's active
users -- the fix for the live bug in ENTITY_RESOLUTION_PLAN.md §1: a
Malayalam message named a real person (ഹൈസം, transliterated "Hysam") who
existed in the org as "Hisham", and the assistant's only lookup
(PostgresUserRepository.find_by_full_name_active) is an exact
case-insensitive match -- so every retry failed identically, forever.

Only the wiring lives here now. The scoring itself moved to
name_matching.py when VENDOR became its second caller (Phase 4) -- nothing
about it was ever user-specific. See that module for why near-match scoring
is used here where workforce/matching.py's match_worker deliberately
refuses it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from runtime.entity_resolution.name_matching import NamedCandidate, resolve_name_hint
from workflows.entities import ResolutionOutcome

if TYPE_CHECKING:
    from mesiri.infrastructure.postgres.database import PostgresDatabase


class MemberNameResolutionService:
    """Wires resolve_name_hint to the org's real active-user roster."""

    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    async def resolve(self, *, organization_id: str, name_hint: str) -> ResolutionOutcome:
        candidates = await self._list_active(organization_id)
        return resolve_name_hint(name_hint, candidates)

    async def get_active_display_name(self, *, organization_id: str, entity_id: str) -> str | None:
        """The current full_name for ``entity_id``, or None if it no longer
        names an active user in this org -- a candidate offered in a picker
        may have been deactivated in the gap between the offer and the tap;
        this re-check is what lets the caller treat that honestly as an
        expired selection rather than trusting a stale id."""
        candidates = await self._list_active(organization_id)
        match = next((c for c in candidates if c.entity_id == entity_id), None)
        return match.display_name if match else None

    async def _list_active(self, organization_id: str) -> list[NamedCandidate]:
        import uuid

        from mesiri.infrastructure.postgres.repositories.users import PostgresUserRepository

        async with self._db.transaction() as conn:
            repo = PostgresUserRepository(conn)
            active = await repo.list_active(uuid.UUID(organization_id))
        return [NamedCandidate(entity_id=str(u.id), display_name=u.full_name) for u in active]
