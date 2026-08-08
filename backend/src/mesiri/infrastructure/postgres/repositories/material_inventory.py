"""PostgreSQL implementation of mesiri.application.materials.inventory.MaterialInventoryReader.

Read-only -- computed fresh from material_receipts/material_usage on every
call, per migration 0180's decision not to maintain a separate stock table.
Groups by exact `material_name` text (material_id is not populated by the
write path yet -- see material_execution.py's INSERT columns), so a
grade/type must already be a distinct name (e.g. "OPC Cement" vs "PPC
Cement") for it to be counted separately.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from mesiri.application.materials.inventory import MaterialInventoryReader

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


class PostgresMaterialInventoryReader(MaterialInventoryReader):
    async def get_available_quantity(
        self,
        conn: AsyncConnection,
        *,
        organization_id: str,
        project_id: str | None,
        site_id: str | None,
        material_name: str,
    ) -> Decimal:
        from sqlalchemy import text

        params: dict[str, object] = {
            "organization_id": uuid.UUID(organization_id),
            "material_name": material_name,
        }

        if site_id is not None:
            scope_clause = "site_id = :site_id"
            params["site_id"] = uuid.UUID(site_id)
        else:
            # No site on this report -- compare only against other site-less
            # rows for the project, not the project's site-tagged rows too.
            scope_clause = "project_id = :project_id AND site_id IS NULL"
            params["project_id"] = uuid.UUID(project_id) if project_id else None

        received = (
            await conn.execute(
                text(
                    "SELECT COALESCE(SUM(quantity), 0) FROM material_receipts "
                    f"WHERE organization_id = :organization_id AND {scope_clause} "
                    "AND material_name = :material_name"
                ),
                params,
            )
        ).scalar_one()

        used = (
            await conn.execute(
                text(
                    "SELECT COALESCE(SUM(quantity), 0) FROM material_usage "
                    f"WHERE organization_id = :organization_id AND {scope_clause} "
                    "AND material_name = :material_name"
                ),
                params,
            )
        ).scalar_one()

        return Decimal(str(received)) - Decimal(str(used))
