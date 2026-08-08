"""Resolve a Progress command's unit text against units_of_measure/unit_aliases.

Defense-in-depth guard, mirroring application/materials/resolution.py: the
WhatsApp assistant's resolution gate (workflows/shared/resolve_location.py
etc., per the plan's §1B.2) should normally have already filled `unit_id` on
each quantity before confirmation. This resolver re-validates, or attempts
one last exact-match/alias resolution if a command somehow reaches the
Handler unresolved.

No catalog to resolve `work_type` against — it is free text in V1 (plan open
decision #4) — so unlike Material, this resolver only ever touches units.
Reuses `UnitsOfMeasureRepository` (0290) rather than building a second
lookup; adding a Progress-specific unit table would be exactly the kind of
duplicate abstraction `AGENTS.md`'s Module Placement Log exists to prevent.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mesiri.infrastructure.postgres.repositories.materials import UnitsOfMeasureRepository
from mesiri_contracts.application.commands.progress import ActivityQuantityInput

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class QuantityResolutionResult:
    unit_id: uuid.UUID | None
    reason: str | None  # None means resolved cleanly


class ProgressUnitResolver(ABC):
    @abstractmethod
    async def resolve_quantity(
        self, conn: AsyncConnection, quantity: ActivityQuantityInput
    ) -> QuantityResolutionResult: ...


class PostgresProgressUnitResolver(ProgressUnitResolver):
    async def resolve_quantity(
        self, conn: AsyncConnection, quantity: ActivityQuantityInput
    ) -> QuantityResolutionResult:
        units_repo = UnitsOfMeasureRepository(conn)

        unit: dict | None
        if quantity.unit_id is not None:
            unit = await units_repo.get_by_id(uuid.UUID(quantity.unit_id))
        else:
            unit = await units_repo.resolve_alias(quantity.unit)

        if unit is None or not unit["is_active"]:
            return QuantityResolutionResult(
                unit_id=None, reason=f"unit '{quantity.unit}' is not a recognized unit"
            )
        return QuantityResolutionResult(unit_id=unit["id"], reason=None)
