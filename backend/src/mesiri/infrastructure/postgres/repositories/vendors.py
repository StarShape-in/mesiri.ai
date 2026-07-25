from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from mesiri.domains.vendors.entities import Vendor

_vendors = sa.Table(
    "vendors",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("name", sa.String),
    sa.Column("status", sa.String),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", sa.UUID(as_uuid=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    sa.Column("updated_by", sa.UUID(as_uuid=True)),
)


def _row_to_vendor(row) -> Vendor:
    return Vendor(id=row.id, organization_id=row.organization_id, name=row.name, status=row.status)


class PostgresVendorRepository:
    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def list_active(self, organization_id: uuid.UUID) -> list[Vendor]:
        stmt = (
            sa.select(_vendors)
            .where(_vendors.c.organization_id == organization_id, _vendors.c.status == "active")
            .order_by(_vendors.c.name)
        )
        res = await self.conn.execute(stmt)
        return [_row_to_vendor(r) for r in res.mappings().all()]

    async def get_by_id(self, organization_id: uuid.UUID, vendor_id: uuid.UUID) -> Vendor | None:
        stmt = sa.select(_vendors).where(
            _vendors.c.id == vendor_id, _vendors.c.organization_id == organization_id
        )
        res = await self.conn.execute(stmt)
        row = res.mappings().first()
        return _row_to_vendor(row) if row else None

    async def find_by_name_exact_active(
        self, organization_id: uuid.UUID, name: str
    ) -> Vendor | None:
        """Case-insensitive exact match against active vendors only."""
        stmt = sa.select(_vendors).where(
            _vendors.c.organization_id == organization_id,
            _vendors.c.status == "active",
            sa.func.lower(_vendors.c.name) == name.strip().lower(),
        )
        res = await self.conn.execute(stmt)
        row = res.mappings().first()
        return _row_to_vendor(row) if row else None

    async def create(
        self, organization_id: uuid.UUID, name: str, *, created_by: uuid.UUID
    ) -> Vendor:
        """Create-on-first-use: a new vendor name typed/spoken over WhatsApp
        becomes a real vendor row immediately, unlike expense_categories'
        single shared "Uncategorized" fallback — every distinct vendor name
        is itself worth keeping, not merged into one bucket. ON CONFLICT
        DO NOTHING on the (organization_id, name) unique constraint makes a
        concurrent first-use race safe, mirroring get_or_create_default."""
        new_id = uuid.uuid4()
        await self.conn.execute(
            sa.text(
                "INSERT INTO vendors (id, organization_id, name, status, created_by) "
                "VALUES (:id, :organization_id, :name, 'active', :created_by) "
                "ON CONFLICT (organization_id, name) DO NOTHING"
            ),
            {
                "id": new_id,
                "organization_id": organization_id,
                "name": name,
                "created_by": created_by,
            },
        )
        existing = await self.find_by_name_exact_active(organization_id, name)
        assert existing is not None
        return existing
