"""Material inventory read service (wiring layer only).

Adapts the backend's PostgresMaterialReadRepository (already used by the
mobile app's /materials/inventory endpoint) into a plain async method the
inbound journey can call. Lives in runtime/ because that's the one layer
allowed to import concrete backend infrastructure directly -- the same
justification runtime/dependencies.py already relies on for the material
execution wiring.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mesiri.infrastructure.postgres.database import PostgresDatabase

# Reported unit spelling varies by message ("bag" vs "bags" vs "sack") even
# though it's the same real-world unit -- material_receipts/material_usage
# store whatever string extraction produced, so stock_levels groups by the
# raw (material_name, unit) pair and the same material can show up as
# several separate lines. Merged here at read time rather than backfilling
# already-stored rows.
_UNIT_ALIASES: dict[str, str] = {
    "bag": "bags",
    "bags": "bags",
    "sack": "bags",
    "sacks": "bags",
    "kg": "kg",
    "kgs": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "ton": "tons",
    "tons": "tons",
    "tonne": "tons",
    "tonnes": "tons",
    "litre": "litres",
    "liter": "litres",
    "litres": "litres",
    "liters": "litres",
    "piece": "pieces",
    "pieces": "pieces",
    "pc": "pieces",
    "pcs": "pieces",
    "roll": "rolls",
    "rolls": "rolls",
    "box": "boxes",
    "boxes": "boxes",
}


def _canonical_unit(unit: str) -> str:
    return _UNIT_ALIASES.get(unit.strip().lower(), unit.strip().lower())


class MaterialInventoryQueryService:
    """Read-only: never opens a write transaction, never mutates state."""

    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    async def query(
        self,
        *,
        organization_id: str,
        project_id: str | None,
        site_id: str | None,
        material_name: str | None,
    ) -> list[dict[str, Any]]:
        """Stock levels for the given scope, optionally filtered to one material
        (substring match). Returns plain JSON-safe dicts: material_name, unit,
        received, used, current_stock -- Decimal/UUID values are never leaked."""
        from mesiri.infrastructure.postgres.repositories.materials import (
            PostgresMaterialReadRepository,
        )

        async with self._db.transaction() as conn:
            repo = PostgresMaterialReadRepository(conn)
            rows = await repo.get_stock_levels(
                organization_id=uuid.UUID(organization_id),
                project_ids={uuid.UUID(project_id)} if project_id else None,
                site_id=uuid.UUID(site_id) if site_id else None,
            )

        # Merge by (material_name lowercased, canonical unit) so "cement/bag",
        # "cement/bags", and "cement/sack" become one summed line instead of
        # three -- see _UNIT_ALIASES above.
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            name_key = row["material_name"].strip().lower()
            unit = _canonical_unit(row["unit"])
            key = (name_key, unit)
            entry = merged.setdefault(
                key,
                {
                    "material_name": row["material_name"],
                    "unit": unit,
                    "received": 0.0,
                    "used": 0.0,
                    "current_stock": 0.0,
                },
            )
            entry["received"] += float(row["total_received"])
            entry["used"] += float(row["total_used"])
            entry["current_stock"] += float(row["current_stock"])

        levels = list(merged.values())

        if material_name:
            needle = material_name.strip().lower()
            levels = [lvl for lvl in levels if needle in lvl["material_name"].lower()]

        return levels
