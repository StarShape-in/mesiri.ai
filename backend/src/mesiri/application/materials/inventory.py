"""Material inventory reader port (M8+).

Defines the read-only contract for estimating how much of a material is on
site right now: everything confirmed as received, minus everything confirmed
as used. This is a live calculation over material_receipts/material_usage,
never a separately stored balance (see migration 0180's docstring for why
no stock table exists). Informational only -- nothing in this codebase
blocks a usage report on this number; callers decide what to do with it.

Scoped to `site_id` when the caller knows one, falling back to `project_id`
(matched against site-less rows only) when it doesn't -- materials can't
move between sites without a real transfer, which isn't modelled yet.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


class MaterialInventoryReader(ABC):
    """Reads the estimated on-site quantity for one material, by exact name."""

    @abstractmethod
    async def get_available_quantity(
        self,
        conn: AsyncConnection,
        *,
        organization_id: str,
        project_id: str | None,
        site_id: str | None,
        material_name: str,
    ) -> Decimal:
        """Confirmed receipts minus confirmed usage for this exact material name."""
        ...
