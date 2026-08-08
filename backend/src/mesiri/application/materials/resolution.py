"""Resolve a Material command's material_name/unit against the catalog + units_of_measure.

Defense-in-depth guard: the *primary* resolution/disambiguation UX lives in
the WhatsApp assistant's deterministic gate chain (runtime/inbound_journey.py),
which should normally have already filled `material_id`/`unit_id` on the
canonical event before confirmation. This resolver re-validates (or, if a
command somehow reaches the Handler unresolved, attempts one last exact-match
resolution) so nothing gets persisted against a catalog entry that doesn't
exist, is inactive, or whose Stock Unit doesn't match — mirroring the REST
router's `_resolve_and_validate_material_unit`.

No fuzzy matching or auto-create here — ambiguity is surfaced upstream as a
picker; by the time a command reaches this module, "ambiguous" is already a
rejection, not a guess.

`MaterialResolver` is an injectable port (mirrors MaterialExecutionRepository
in repository.py) so Handler unit tests can supply a fake instead of hitting
Postgres — see application/materials/fakes.py: FakeMaterialResolver.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mesiri.application.materials.repository import MaterialCommand
from mesiri.infrastructure.postgres.repositories.materials import (
    PostgresMaterialCatalogRepository,
    UnitsOfMeasureRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class ResolutionResult:
    material_id: uuid.UUID | None
    unit_id: uuid.UUID | None
    reasons: list[str]


class MaterialResolver(ABC):
    @abstractmethod
    async def resolve(self, conn: AsyncConnection, cmd: MaterialCommand) -> ResolutionResult: ...


class PostgresMaterialResolver(MaterialResolver):
    async def resolve(self, conn: AsyncConnection, cmd: MaterialCommand) -> ResolutionResult:
        reasons: list[str] = []
        organization_id = uuid.UUID(cmd.organization_id)
        catalog_repo = PostgresMaterialCatalogRepository(conn)
        units_repo = UnitsOfMeasureRepository(conn)

        material: dict | None
        if cmd.material_id is not None:
            material = await catalog_repo.get_by_id(organization_id, uuid.UUID(cmd.material_id))
        else:
            material = await catalog_repo.find_by_name_exact_active(organization_id, cmd.material_name)

        if material is None or not material["is_active"]:
            reasons.append(f"material '{cmd.material_name}' not found in catalog")
            return ResolutionResult(material_id=None, unit_id=None, reasons=reasons)

        unit: dict | None
        if cmd.unit_id is not None:
            unit = await units_repo.get_by_id(uuid.UUID(cmd.unit_id))
        else:
            unit = await units_repo.resolve_alias(cmd.unit)

        if unit is None or not unit["is_active"]:
            reasons.append(f"unit '{cmd.unit}' is not a recognized unit")
            return ResolutionResult(material_id=material["id"], unit_id=None, reasons=reasons)

        if material["default_unit_id"] is not None and unit["id"] != material["default_unit_id"]:
            reasons.append(
                f"unit '{cmd.unit}' does not match {material['name']}'s Stock Unit "
                f"({material['default_unit']})"
            )
            return ResolutionResult(material_id=material["id"], unit_id=unit["id"], reasons=reasons)

        return ResolutionResult(material_id=material["id"], unit_id=unit["id"], reasons=[])
