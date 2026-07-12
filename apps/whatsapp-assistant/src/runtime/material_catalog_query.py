"""Material catalog / units-of-measure read service (wiring layer only).

Same shape and justification as runtime/inventory_query.py: adapts the
backend's PostgresMaterialCatalogRepository/UnitsOfMeasureRepository into
plain async methods the inbound journey's material/unit resolution gate can
call, without the WhatsApp assistant depending on backend infrastructure
anywhere outside runtime/.

No fuzzy scoring beyond the repository's ILIKE substring match, no
auto-create, no unit conversion -- ambiguity/absence is returned as plain
data (0, 1, or many candidates) and the caller (runtime/inbound_journey.py)
decides whether that means "resolved silently" or "ask the user".
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mesiri.infrastructure.postgres.database import PostgresDatabase


class MaterialCatalogQueryService:
    """Read-only: never opens a write transaction, never mutates state."""

    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    async def find_materials(self, *, organization_id: str, name: str) -> list[dict[str, Any]]:
        """Active catalog matches for `name`. An exact (case-insensitive) match
        always wins outright and is returned alone; otherwise substring
        candidates (0, 1, or many) so the caller can ask/report accordingly."""
        from mesiri.infrastructure.postgres.repositories.materials import (
            PostgresMaterialCatalogRepository,
        )

        org = uuid.UUID(organization_id)
        async with self._db.transaction() as conn:
            repo = PostgresMaterialCatalogRepository(conn)
            exact = await repo.find_by_name_exact_active(org, name)
            if exact is not None:
                return [exact]
            return await repo.find_by_name_fuzzy(org, name, limit=10)

    async def list_active_materials(self, *, organization_id: str) -> list[dict[str, Any]]:
        """Fallback candidate list when nothing matched the reported name at
        all -- still gives the user something to pick from."""
        from mesiri.infrastructure.postgres.repositories.materials import (
            PostgresMaterialCatalogRepository,
        )

        async with self._db.transaction() as conn:
            repo = PostgresMaterialCatalogRepository(conn)
            items, _total = await repo.list_materials(
                organization_id=uuid.UUID(organization_id), is_active=True, limit=10
            )
            return items

    async def get_material(self, *, organization_id: str, material_id: str) -> dict[str, Any] | None:
        from mesiri.infrastructure.postgres.repositories.materials import (
            PostgresMaterialCatalogRepository,
        )

        async with self._db.transaction() as conn:
            repo = PostgresMaterialCatalogRepository(conn)
            return await repo.get_by_id(uuid.UUID(organization_id), uuid.UUID(material_id))

    async def resolve_unit(self, text: str) -> dict[str, Any] | None:
        """Resolve free text (exact code or known alias) to its canonical unit."""
        from mesiri.infrastructure.postgres.repositories.materials import (
            UnitsOfMeasureRepository,
        )

        async with self._db.transaction() as conn:
            repo = UnitsOfMeasureRepository(conn)
            return await repo.resolve_alias(text)

    async def get_unit(self, unit_id: str) -> dict[str, Any] | None:
        from mesiri.infrastructure.postgres.repositories.materials import (
            UnitsOfMeasureRepository,
        )

        async with self._db.transaction() as conn:
            repo = UnitsOfMeasureRepository(conn)
            return await repo.get_by_id(uuid.UUID(unit_id))
