from __future__ import annotations

import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

_timeline_entries = sa.Table(
    "timeline_entries",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("project_id", sa.UUID(as_uuid=True)),
    sa.Column("site_id", sa.UUID(as_uuid=True)),
    sa.Column("event_type", sa.String),
    sa.Column("summary", sa.String),
    sa.Column("payload", sa.JSON),
    sa.Column("occurred_at", sa.DateTime(timezone=True)),
    sa.Column("correlation_id", sa.String),
    sa.Column("source_aggregate_type", sa.String),
    sa.Column("source_aggregate_id", sa.UUID(as_uuid=True)),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)


class PostgresTimelineReadRepository:
    """PostgreSQL read-side repository for the Timeline feed.

    Reads only timeline_entries — the event-sourced projection table. Never
    queries material_receipts/expenses/etc. directly (see
    mesiri.events.consumers.timeline_projector, which is the sole writer).
    """

    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def list_entries(
        self,
        organization_id: uuid.UUID,
        project_ids: set[uuid.UUID] | None = None,
        site_id: uuid.UUID | None = None,
        event_type: str | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """List timeline entries matching parameters, with total count."""
        where_clauses = [_timeline_entries.c.organization_id == organization_id]
        if project_ids is not None:
            where_clauses.append(_timeline_entries.c.project_id.in_(project_ids))
        if site_id is not None:
            where_clauses.append(_timeline_entries.c.site_id == site_id)
        if event_type is not None:
            where_clauses.append(_timeline_entries.c.event_type == event_type)
        if date_from is not None:
            where_clauses.append(
                sa.cast(_timeline_entries.c.occurred_at, sa.Date) >= date_from
            )
        if date_to is not None:
            where_clauses.append(
                sa.cast(_timeline_entries.c.occurred_at, sa.Date) <= date_to
            )

        count_stmt = sa.select(sa.func.count()).select_from(_timeline_entries).where(*where_clauses)
        total = (await self.conn.execute(count_stmt)).scalar_one()

        stmt = (
            sa.select(_timeline_entries)
            .where(*where_clauses)
            .order_by(_timeline_entries.c.occurred_at.desc(), _timeline_entries.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.conn.execute(stmt)
        items = [dict(r) for r in res.mappings().all()]
        return items, total

    async def day_summary(
        self,
        organization_id: uuid.UUID,
        project_ids: set[uuid.UUID] | None = None,
        site_id: uuid.UUID | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
    ) -> list[dict]:
        """Aggregate entry counts per day per event_type, for sticky-header UI."""
        where_clauses = [_timeline_entries.c.organization_id == organization_id]
        if project_ids is not None:
            where_clauses.append(_timeline_entries.c.project_id.in_(project_ids))
        if site_id is not None:
            where_clauses.append(_timeline_entries.c.site_id == site_id)
        if date_from is not None:
            where_clauses.append(
                sa.cast(_timeline_entries.c.occurred_at, sa.Date) >= date_from
            )
        if date_to is not None:
            where_clauses.append(
                sa.cast(_timeline_entries.c.occurred_at, sa.Date) <= date_to
            )

        day_col = sa.cast(_timeline_entries.c.occurred_at, sa.Date).label("day")
        stmt = (
            sa.select(
                day_col,
                _timeline_entries.c.event_type,
                sa.func.count().label("count"),
            )
            .where(*where_clauses)
            .group_by(day_col, _timeline_entries.c.event_type)
            .order_by(day_col.desc())
        )
        res = await self.conn.execute(stmt)
        return [dict(r) for r in res.mappings().all()]
