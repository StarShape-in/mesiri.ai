from __future__ import annotations

import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

_material_receipts = sa.Table(
    "material_receipts",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("project_id", sa.UUID(as_uuid=True)),
    sa.Column("site_id", sa.UUID(as_uuid=True)),
    sa.Column("material_name", sa.String),
    sa.Column("quantity", sa.Numeric),
    sa.Column("unit", sa.String),
    sa.Column("unit_cost", sa.Numeric),
    sa.Column("total_cost", sa.Numeric),
    sa.Column("supplier", sa.String),
    sa.Column("occurred_date", sa.Date),
    sa.Column("occurred_time", sa.Time),
    sa.Column("correlation_id", sa.String),
    sa.Column("source", sa.String),
    sa.Column("occurred_date_source", sa.String),
    sa.Column("material_id", sa.UUID(as_uuid=True)),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", sa.UUID(as_uuid=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    sa.Column("updated_by", sa.UUID(as_uuid=True)),
)

_material_usage = sa.Table(
    "material_usage",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("project_id", sa.UUID(as_uuid=True)),
    sa.Column("site_id", sa.UUID(as_uuid=True)),
    sa.Column("material_name", sa.String),
    sa.Column("quantity", sa.Numeric),
    sa.Column("unit", sa.String),
    sa.Column("work_item", sa.String),
    sa.Column("occurred_date", sa.Date),
    sa.Column("occurred_time", sa.Time),
    sa.Column("correlation_id", sa.String),
    sa.Column("source", sa.String),
    sa.Column("occurred_date_source", sa.String),
    sa.Column("material_id", sa.UUID(as_uuid=True)),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", sa.UUID(as_uuid=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    sa.Column("updated_by", sa.UUID(as_uuid=True)),
)


class PostgresMaterialReadRepository:
    """PostgreSQL read-side repository for material inflows, outflows, and stock levels."""

    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def list_receipts(
        self,
        organization_id: uuid.UUID,
        project_ids: set[uuid.UUID] | None = None,
        site_id: uuid.UUID | None = None,
        material_name: str | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """List material receipts (inflows) matching parameters, with total count."""
        where_clauses = [_material_receipts.c.organization_id == organization_id]
        if project_ids is not None:
            where_clauses.append(_material_receipts.c.project_id.in_(project_ids))
        if site_id is not None:
            where_clauses.append(_material_receipts.c.site_id == site_id)
        if material_name is not None:
            where_clauses.append(_material_receipts.c.material_name.ilike(f"%{material_name}%"))
        if date_from is not None:
            where_clauses.append(_material_receipts.c.occurred_date >= date_from)
        if date_to is not None:
            where_clauses.append(_material_receipts.c.occurred_date <= date_to)

        # Count query
        count_stmt = sa.select(sa.func.count()).select_from(_material_receipts).where(*where_clauses)
        total = (await self.conn.execute(count_stmt)).scalar_one()

        # Selection query
        stmt = (
            sa.select(_material_receipts)
            .where(*where_clauses)
            .order_by(_material_receipts.c.occurred_date.desc(), _material_receipts.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.conn.execute(stmt)
        items = [dict(r) for r in res.mappings().all()]
        return items, total

    async def list_usage(
        self,
        organization_id: uuid.UUID,
        project_ids: set[uuid.UUID] | None = None,
        site_id: uuid.UUID | None = None,
        material_name: str | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """List material usages (outflows) matching parameters, with total count."""
        where_clauses = [_material_usage.c.organization_id == organization_id]
        if project_ids is not None:
            where_clauses.append(_material_usage.c.project_id.in_(project_ids))
        if site_id is not None:
            where_clauses.append(_material_usage.c.site_id == site_id)
        if material_name is not None:
            where_clauses.append(_material_usage.c.material_name.ilike(f"%{material_name}%"))
        if date_from is not None:
            where_clauses.append(_material_usage.c.occurred_date >= date_from)
        if date_to is not None:
            where_clauses.append(_material_usage.c.occurred_date <= date_to)

        # Count query
        count_stmt = sa.select(sa.func.count()).select_from(_material_usage).where(*where_clauses)
        total = (await self.conn.execute(count_stmt)).scalar_one()

        # Selection query
        stmt = (
            sa.select(_material_usage)
            .where(*where_clauses)
            .order_by(_material_usage.c.occurred_date.desc(), _material_usage.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.conn.execute(stmt)
        items = [dict(r) for r in res.mappings().all()]
        return items, total

    async def get_stock_levels(
        self,
        organization_id: uuid.UUID,
        project_ids: set[uuid.UUID] | None = None,
        site_id: uuid.UUID | None = None,
    ) -> list[dict]:
        """Retrieve aggregated inventory stock levels (inflows minus outflows)."""
        # Receipts CTE
        receipts_stmt = sa.select(
            _material_receipts.c.organization_id,
            _material_receipts.c.project_id,
            _material_receipts.c.site_id,
            _material_receipts.c.material_name,
            _material_receipts.c.unit,
            sa.func.sum(_material_receipts.c.quantity).label("total_received")
        ).where(_material_receipts.c.organization_id == organization_id)

        if project_ids is not None:
            receipts_stmt = receipts_stmt.where(_material_receipts.c.project_id.in_(project_ids))
        if site_id is not None:
            receipts_stmt = receipts_stmt.where(_material_receipts.c.site_id == site_id)

        receipts_stmt = receipts_stmt.group_by(
            _material_receipts.c.organization_id,
            _material_receipts.c.project_id,
            _material_receipts.c.site_id,
            _material_receipts.c.material_name,
            _material_receipts.c.unit
        )
        receipts_cte = receipts_stmt.cte("receipts_agg")

        # Usage CTE
        usage_stmt = sa.select(
            _material_usage.c.organization_id,
            _material_usage.c.project_id,
            _material_usage.c.site_id,
            _material_usage.c.material_name,
            _material_usage.c.unit,
            sa.func.sum(_material_usage.c.quantity).label("total_used")
        ).where(_material_usage.c.organization_id == organization_id)

        if project_ids is not None:
            usage_stmt = usage_stmt.where(_material_usage.c.project_id.in_(project_ids))
        if site_id is not None:
            usage_stmt = usage_stmt.where(_material_usage.c.site_id == site_id)

        usage_stmt = usage_stmt.group_by(
            _material_usage.c.organization_id,
            _material_usage.c.project_id,
            _material_usage.c.site_id,
            _material_usage.c.material_name,
            _material_usage.c.unit
        )
        usage_cte = usage_stmt.cte("usage_agg")

        # FULL OUTER JOIN condition (incorporating site_id null-safe comparisons)
        join_cond = sa.and_(
            receipts_cte.c.organization_id == usage_cte.c.organization_id,
            receipts_cte.c.project_id == usage_cte.c.project_id,
            sa.or_(
                receipts_cte.c.site_id == usage_cte.c.site_id,
                sa.and_(receipts_cte.c.site_id.is_(None), usage_cte.c.site_id.is_(None))
            ),
            receipts_cte.c.material_name == usage_cte.c.material_name,
            receipts_cte.c.unit == usage_cte.c.unit
        )

        # Outer select executing net stock arithmetic
        select_stmt = sa.select(
            sa.func.coalesce(receipts_cte.c.organization_id, usage_cte.c.organization_id).label("organization_id"),
            sa.func.coalesce(receipts_cte.c.project_id, usage_cte.c.project_id).label("project_id"),
            sa.func.coalesce(receipts_cte.c.site_id, usage_cte.c.site_id).label("site_id"),
            sa.func.coalesce(receipts_cte.c.material_name, usage_cte.c.material_name).label("material_name"),
            sa.func.coalesce(receipts_cte.c.unit, usage_cte.c.unit).label("unit"),
            sa.func.coalesce(receipts_cte.c.total_received, 0).label("total_received"),
            sa.func.coalesce(usage_cte.c.total_used, 0).label("total_used"),
            (sa.func.coalesce(receipts_cte.c.total_received, 0) - sa.func.coalesce(usage_cte.c.total_used, 0)).label("current_stock")
        ).select_from(
            receipts_cte.join(usage_cte, join_cond, full=True)
        ).order_by(
            sa.func.coalesce(receipts_cte.c.material_name, usage_cte.c.material_name).asc()
        )

        res = await self.conn.execute(select_stmt)
        return [dict(r) for r in res.mappings().all()]
