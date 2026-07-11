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
    sa.Column("movement_reason", sa.String),
    sa.Column("notes", sa.String),
    sa.Column("reverses_movement_id", sa.UUID(as_uuid=True)),
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
    sa.Column("movement_reason", sa.String),
    sa.Column("notes", sa.String),
    sa.Column("reverses_movement_id", sa.UUID(as_uuid=True)),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", sa.UUID(as_uuid=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    sa.Column("updated_by", sa.UUID(as_uuid=True)),
)

_materials_catalog = sa.Table(
    "materials_catalog",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("name", sa.String),
    sa.Column("default_unit", sa.String),
    sa.Column("category", sa.String),
    sa.Column("sku", sa.String),
    sa.Column("is_active", sa.Boolean),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", sa.UUID(as_uuid=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    sa.Column("updated_by", sa.UUID(as_uuid=True)),
)


def _receipt_where(
    organization_id: uuid.UUID,
    project_ids: set[uuid.UUID] | None,
    site_id: uuid.UUID | None,
    material_id: uuid.UUID | None,
    material_name: str | None,
    movement_reason: str | None,
    source: str | None,
    recorded_by_user_id: uuid.UUID | None,
    date_from: datetime.date | None,
    date_to: datetime.date | None,
) -> list:
    where_clauses = [_material_receipts.c.organization_id == organization_id]
    if project_ids is not None:
        where_clauses.append(_material_receipts.c.project_id.in_(project_ids))
    if site_id is not None:
        where_clauses.append(_material_receipts.c.site_id == site_id)
    if material_id is not None:
        where_clauses.append(_material_receipts.c.material_id == material_id)
    if material_name is not None:
        where_clauses.append(_material_receipts.c.material_name.ilike(f"%{material_name}%"))
    if movement_reason is not None:
        where_clauses.append(_material_receipts.c.movement_reason == movement_reason)
    if source is not None:
        where_clauses.append(_material_receipts.c.source == source)
    if recorded_by_user_id is not None:
        where_clauses.append(_material_receipts.c.created_by == recorded_by_user_id)
    if date_from is not None:
        where_clauses.append(_material_receipts.c.occurred_date >= date_from)
    if date_to is not None:
        where_clauses.append(_material_receipts.c.occurred_date <= date_to)
    return where_clauses


def _usage_where(
    organization_id: uuid.UUID,
    project_ids: set[uuid.UUID] | None,
    site_id: uuid.UUID | None,
    material_id: uuid.UUID | None,
    material_name: str | None,
    movement_reason: str | None,
    source: str | None,
    recorded_by_user_id: uuid.UUID | None,
    date_from: datetime.date | None,
    date_to: datetime.date | None,
) -> list:
    where_clauses = [_material_usage.c.organization_id == organization_id]
    if project_ids is not None:
        where_clauses.append(_material_usage.c.project_id.in_(project_ids))
    if site_id is not None:
        where_clauses.append(_material_usage.c.site_id == site_id)
    if material_id is not None:
        where_clauses.append(_material_usage.c.material_id == material_id)
    if material_name is not None:
        where_clauses.append(_material_usage.c.material_name.ilike(f"%{material_name}%"))
    if movement_reason is not None:
        where_clauses.append(_material_usage.c.movement_reason == movement_reason)
    if source is not None:
        where_clauses.append(_material_usage.c.source == source)
    if recorded_by_user_id is not None:
        where_clauses.append(_material_usage.c.created_by == recorded_by_user_id)
    if date_from is not None:
        where_clauses.append(_material_usage.c.occurred_date >= date_from)
    if date_to is not None:
        where_clauses.append(_material_usage.c.occurred_date <= date_to)
    return where_clauses


class PostgresMaterialReadRepository:
    """PostgreSQL read-side repository for material inflows, outflows, and stock levels."""

    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def list_receipts(
        self,
        organization_id: uuid.UUID,
        project_ids: set[uuid.UUID] | None = None,
        site_id: uuid.UUID | None = None,
        material_id: uuid.UUID | None = None,
        material_name: str | None = None,
        movement_reason: str | None = None,
        source: str | None = None,
        recorded_by_user_id: uuid.UUID | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """List material receipts (inflows) matching parameters, with total count."""
        where_clauses = _receipt_where(
            organization_id,
            project_ids,
            site_id,
            material_id,
            material_name,
            movement_reason,
            source,
            recorded_by_user_id,
            date_from,
            date_to,
        )

        count_stmt = (
            sa.select(sa.func.count()).select_from(_material_receipts).where(*where_clauses)
        )
        total = (await self.conn.execute(count_stmt)).scalar_one()

        stmt = (
            sa.select(_material_receipts)
            .where(*where_clauses)
            .order_by(
                _material_receipts.c.occurred_date.desc(), _material_receipts.c.created_at.desc()
            )
            .limit(limit)
            .offset(offset)
        )
        res = await self.conn.execute(stmt)
        items = [dict(r) for r in res.mappings().all()]
        return items, total

    async def get_receipt(self, organization_id: uuid.UUID, receipt_id: uuid.UUID) -> dict | None:
        stmt = sa.select(_material_receipts).where(
            _material_receipts.c.id == receipt_id,
            _material_receipts.c.organization_id == organization_id,
        )
        res = await self.conn.execute(stmt)
        row = res.mappings().first()
        return dict(row) if row else None

    async def list_usage(
        self,
        organization_id: uuid.UUID,
        project_ids: set[uuid.UUID] | None = None,
        site_id: uuid.UUID | None = None,
        material_id: uuid.UUID | None = None,
        material_name: str | None = None,
        movement_reason: str | None = None,
        source: str | None = None,
        recorded_by_user_id: uuid.UUID | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """List material usages (outflows) matching parameters, with total count."""
        where_clauses = _usage_where(
            organization_id,
            project_ids,
            site_id,
            material_id,
            material_name,
            movement_reason,
            source,
            recorded_by_user_id,
            date_from,
            date_to,
        )

        count_stmt = sa.select(sa.func.count()).select_from(_material_usage).where(*where_clauses)
        total = (await self.conn.execute(count_stmt)).scalar_one()

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

    async def get_usage(self, organization_id: uuid.UUID, usage_id: uuid.UUID) -> dict | None:
        stmt = sa.select(_material_usage).where(
            _material_usage.c.id == usage_id,
            _material_usage.c.organization_id == organization_id,
        )
        res = await self.conn.execute(stmt)
        row = res.mappings().first()
        return dict(row) if row else None

    async def get_stock_levels(
        self,
        organization_id: uuid.UUID,
        project_ids: set[uuid.UUID] | None = None,
        site_id: uuid.UUID | None = None,
        material_id: uuid.UUID | None = None,
    ) -> list[dict]:
        """Retrieve aggregated inventory stock levels (inflows minus outflows)."""
        receipts_stmt = sa.select(
            _material_receipts.c.organization_id,
            _material_receipts.c.project_id,
            _material_receipts.c.site_id,
            _material_receipts.c.material_id,
            _material_receipts.c.material_name,
            _material_receipts.c.unit,
            sa.func.sum(_material_receipts.c.quantity).label("total_received"),
            sa.func.max(_material_receipts.c.created_at).label("last_receipt_at"),
        ).where(_material_receipts.c.organization_id == organization_id)

        if project_ids is not None:
            receipts_stmt = receipts_stmt.where(_material_receipts.c.project_id.in_(project_ids))
        if site_id is not None:
            receipts_stmt = receipts_stmt.where(_material_receipts.c.site_id == site_id)
        if material_id is not None:
            receipts_stmt = receipts_stmt.where(_material_receipts.c.material_id == material_id)

        receipts_stmt = receipts_stmt.group_by(
            _material_receipts.c.organization_id,
            _material_receipts.c.project_id,
            _material_receipts.c.site_id,
            _material_receipts.c.material_id,
            _material_receipts.c.material_name,
            _material_receipts.c.unit,
        )
        receipts_cte = receipts_stmt.cte("receipts_agg")

        usage_stmt = sa.select(
            _material_usage.c.organization_id,
            _material_usage.c.project_id,
            _material_usage.c.site_id,
            _material_usage.c.material_id,
            _material_usage.c.material_name,
            _material_usage.c.unit,
            sa.func.sum(_material_usage.c.quantity).label("total_used"),
            sa.func.max(_material_usage.c.created_at).label("last_usage_at"),
        ).where(_material_usage.c.organization_id == organization_id)

        if project_ids is not None:
            usage_stmt = usage_stmt.where(_material_usage.c.project_id.in_(project_ids))
        if site_id is not None:
            usage_stmt = usage_stmt.where(_material_usage.c.site_id == site_id)
        if material_id is not None:
            usage_stmt = usage_stmt.where(_material_usage.c.material_id == material_id)

        usage_stmt = usage_stmt.group_by(
            _material_usage.c.organization_id,
            _material_usage.c.project_id,
            _material_usage.c.site_id,
            _material_usage.c.material_id,
            _material_usage.c.material_name,
            _material_usage.c.unit,
        )
        usage_cte = usage_stmt.cte("usage_agg")

        join_cond = sa.and_(
            receipts_cte.c.organization_id == usage_cte.c.organization_id,
            receipts_cte.c.project_id == usage_cte.c.project_id,
            sa.or_(
                receipts_cte.c.site_id == usage_cte.c.site_id,
                sa.and_(receipts_cte.c.site_id.is_(None), usage_cte.c.site_id.is_(None)),
            ),
            receipts_cte.c.material_name == usage_cte.c.material_name,
            receipts_cte.c.unit == usage_cte.c.unit,
        )

        current_stock = sa.func.coalesce(receipts_cte.c.total_received, 0) - sa.func.coalesce(
            usage_cte.c.total_used, 0
        )
        # postgres GREATEST() ignores NULL args and only returns NULL if all are NULL
        last_movement_at = sa.func.greatest(
            receipts_cte.c.last_receipt_at, usage_cte.c.last_usage_at
        )

        select_stmt = (
            sa.select(
                sa.func.coalesce(receipts_cte.c.organization_id, usage_cte.c.organization_id).label(
                    "organization_id"
                ),
                sa.func.coalesce(receipts_cte.c.project_id, usage_cte.c.project_id).label(
                    "project_id"
                ),
                sa.func.coalesce(receipts_cte.c.site_id, usage_cte.c.site_id).label("site_id"),
                sa.func.coalesce(receipts_cte.c.material_id, usage_cte.c.material_id).label(
                    "material_id"
                ),
                sa.func.coalesce(receipts_cte.c.material_name, usage_cte.c.material_name).label(
                    "material_name"
                ),
                sa.func.coalesce(receipts_cte.c.unit, usage_cte.c.unit).label("unit"),
                sa.func.coalesce(receipts_cte.c.total_received, 0).label("total_received"),
                sa.func.coalesce(usage_cte.c.total_used, 0).label("total_used"),
                current_stock.label("current_stock"),
                last_movement_at.label("last_movement_at"),
                sa.case(
                    (current_stock < 0, "NEGATIVE_STOCK"),
                    (current_stock == 0, "OUT_OF_STOCK"),
                    else_="AVAILABLE",
                ).label("stock_state"),
            )
            .select_from(receipts_cte.join(usage_cte, join_cond, full=True))
            .order_by(
                sa.func.coalesce(receipts_cte.c.material_name, usage_cte.c.material_name).asc()
            )
        )

        res = await self.conn.execute(select_stmt)
        return [dict(r) for r in res.mappings().all()]

    async def get_ledger(
        self,
        organization_id: uuid.UUID,
        site_id: uuid.UUID,
        material_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Chronological IN+OUT movement history for one Site + Material, with running balance.

        Combines both ledger tables into one ordered stream (oldest first) and
        computes a running balance via a window function, then returns the
        page in newest-first order for display while keeping balances correct.
        """
        in_stmt = sa.select(
            _material_receipts.c.id,
            sa.literal("IN").label("direction"),
            _material_receipts.c.movement_reason,
            _material_receipts.c.quantity,
            _material_receipts.c.unit,
            _material_receipts.c.occurred_date,
            _material_receipts.c.occurred_time,
            _material_receipts.c.source,
            _material_receipts.c.notes,
            _material_receipts.c.supplier.label("context"),
            _material_receipts.c.reverses_movement_id,
            _material_receipts.c.created_by,
            _material_receipts.c.created_at,
        ).where(
            _material_receipts.c.organization_id == organization_id,
            _material_receipts.c.site_id == site_id,
            _material_receipts.c.material_id == material_id,
        )
        out_stmt = sa.select(
            _material_usage.c.id,
            sa.literal("OUT").label("direction"),
            _material_usage.c.movement_reason,
            _material_usage.c.quantity,
            _material_usage.c.unit,
            _material_usage.c.occurred_date,
            _material_usage.c.occurred_time,
            _material_usage.c.source,
            _material_usage.c.notes,
            _material_usage.c.work_item.label("context"),
            _material_usage.c.reverses_movement_id,
            _material_usage.c.created_by,
            _material_usage.c.created_at,
        ).where(
            _material_usage.c.organization_id == organization_id,
            _material_usage.c.site_id == site_id,
            _material_usage.c.material_id == material_id,
        )
        combined = sa.union_all(in_stmt, out_stmt).cte("ledger_combined")

        signed_qty = sa.case(
            (combined.c.direction == "IN", combined.c.quantity),
            else_=-combined.c.quantity,
        )
        running_balance = sa.func.sum(signed_qty).over(
            order_by=[combined.c.occurred_date.asc(), combined.c.created_at.asc()]
        )

        with_balance = sa.select(combined, running_balance.label("running_balance")).cte(
            "ledger_with_balance"
        )

        total = (
            await self.conn.execute(sa.select(sa.func.count()).select_from(with_balance))
        ).scalar_one()

        stmt = (
            sa.select(with_balance)
            .order_by(with_balance.c.occurred_date.desc(), with_balance.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.conn.execute(stmt)
        items = [dict(r) for r in res.mappings().all()]
        return items, total


class PostgresMaterialCatalogRepository:
    """PostgreSQL repository for the org-scoped Material catalog."""

    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def list_materials(
        self,
        organization_id: uuid.UUID,
        search: str | None = None,
        is_active: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        where_clauses = [_materials_catalog.c.organization_id == organization_id]
        if search is not None:
            where_clauses.append(_materials_catalog.c.name.ilike(f"%{search}%"))
        if is_active is not None:
            where_clauses.append(_materials_catalog.c.is_active == is_active)

        count_stmt = (
            sa.select(sa.func.count()).select_from(_materials_catalog).where(*where_clauses)
        )
        total = (await self.conn.execute(count_stmt)).scalar_one()

        stmt = (
            sa.select(_materials_catalog)
            .where(*where_clauses)
            .order_by(_materials_catalog.c.name.asc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.conn.execute(stmt)
        items = [dict(r) for r in res.mappings().all()]
        return items, total

    async def get_by_id(self, organization_id: uuid.UUID, material_id: uuid.UUID) -> dict | None:
        stmt = sa.select(_materials_catalog).where(
            _materials_catalog.c.id == material_id,
            _materials_catalog.c.organization_id == organization_id,
        )
        res = await self.conn.execute(stmt)
        row = res.mappings().first()
        return dict(row) if row else None

    async def get_by_name(self, organization_id: uuid.UUID, name: str) -> dict | None:
        stmt = sa.select(_materials_catalog).where(
            _materials_catalog.c.organization_id == organization_id,
            _materials_catalog.c.name == name,
        )
        res = await self.conn.execute(stmt)
        row = res.mappings().first()
        return dict(row) if row else None

    async def create(
        self,
        organization_id: uuid.UUID,
        name: str,
        default_unit: str | None,
        category: str | None,
        sku: str | None,
        created_by: uuid.UUID,
    ) -> dict:
        new_id = uuid.uuid4()
        stmt = sa.insert(_materials_catalog).values(
            id=new_id,
            organization_id=organization_id,
            name=name,
            default_unit=default_unit,
            category=category,
            sku=sku,
            is_active=True,
            created_by=created_by,
        )
        await self.conn.execute(stmt)
        return await self.get_by_id(organization_id, new_id)  # type: ignore[return-value]

    async def get_or_create_by_name(
        self,
        organization_id: uuid.UUID,
        name: str,
        default_unit: str | None,
        created_by: uuid.UUID,
    ) -> dict:
        """Idempotent lookup used by movement-create endpoints to link material_id."""
        existing = await self.get_by_name(organization_id, name)
        if existing is not None:
            return existing
        return await self.create(
            organization_id,
            name,
            default_unit=default_unit,
            category=None,
            sku=None,
            created_by=created_by,
        )
