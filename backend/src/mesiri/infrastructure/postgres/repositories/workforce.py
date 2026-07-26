"""Read/write access for the workforce register and attendance reports.

Companion to labour_execution.py, which owns the *write* path a WhatsApp
confirmation takes (persist_success/persist_rejection against the same four
tables). This file is the dashboard-facing read side, plus the register's
own CRUD (workforce_workers is the one table here that a dashboard writes to
directly, since promoting/editing a worker is not a WhatsApp-confirmed
workflow the way attendance is).

Mirrors materials.py's PostgresMaterialReadRepository for shape: plain
sqlalchemy Core tables, no ORM, every method takes an externally-supplied
connection and never commits.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

_workforce_workers = sa.Table(
    "workforce_workers",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("name", sa.String),
    sa.Column("trade", sa.String),
    sa.Column("worker_type", sa.String),
    sa.Column("default_daily_wage", sa.Numeric),
    sa.Column("contractor", sa.String),
    sa.Column("status", sa.String),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", sa.UUID(as_uuid=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    sa.Column("updated_by", sa.UUID(as_uuid=True)),
)

_labour_attendance_reports = sa.Table(
    "labour_attendance_reports",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("project_id", sa.UUID(as_uuid=True)),
    sa.Column("site_id", sa.UUID(as_uuid=True)),
    sa.Column("occurred_date", sa.Date),
    sa.Column("recorded_via", sa.String),
    sa.Column("notes", sa.Text),
    sa.Column("corrects_report_id", sa.UUID(as_uuid=True)),
    sa.Column("correlation_id", sa.String),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", sa.UUID(as_uuid=True)),
)

_labour_attendance_lines = sa.Table(
    "labour_attendance_lines",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("report_id", sa.UUID(as_uuid=True)),
    sa.Column("worker_id", sa.UUID(as_uuid=True)),
    sa.Column("worker_name", sa.String),
    sa.Column("worker_name_original", sa.String),
    sa.Column("trade", sa.String),
    sa.Column("headcount", sa.Integer),
    sa.Column("daily_wage", sa.Numeric),
    sa.Column("contractor", sa.String),
    sa.Column("activity", sa.String),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)

_labour_attendance_attachments = sa.Table(
    "labour_attendance_attachments",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True)),
    sa.Column("report_id", sa.UUID(as_uuid=True)),
    sa.Column("media_object_key", sa.String),
    sa.Column("attachment_type", sa.String),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", sa.UUID(as_uuid=True)),
)


def _line_totals(lines: list[dict[str, Any]]) -> tuple[int, float]:
    headcount = 0
    cost = 0.0
    for line in lines:
        count = int(line.get("headcount") or 1)
        headcount += count
        wage = line.get("daily_wage")
        if wage is not None:
            cost += float(wage) * count
    return headcount, cost


class PostgresWorkforceReadRepository:
    """Register CRUD (workforce_workers) and attendance report reads."""

    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    # --- Register -----------------------------------------------------

    async def list_workers(
        self,
        *,
        organization_id: uuid.UUID,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions = [_workforce_workers.c.organization_id == organization_id]
        if status is not None:
            conditions.append(_workforce_workers.c.status == status)
        if search:
            conditions.append(_workforce_workers.c.name.ilike(f"%{search}%"))

        total = (
            await self._conn.execute(
                sa.select(sa.func.count()).select_from(_workforce_workers).where(*conditions)
            )
        ).scalar_one()

        rows = (
            await self._conn.execute(
                sa.select(_workforce_workers)
                .where(*conditions)
                .order_by(_workforce_workers.c.name)
                .limit(limit)
                .offset(offset)
            )
        ).mappings().all()
        return [dict(row) for row in rows], int(total)

    async def get_worker(
        self, organization_id: uuid.UUID, worker_id: uuid.UUID
    ) -> dict[str, Any] | None:
        row = (
            await self._conn.execute(
                sa.select(_workforce_workers).where(
                    _workforce_workers.c.organization_id == organization_id,
                    _workforce_workers.c.id == worker_id,
                )
            )
        ).mappings().first()
        return dict(row) if row is not None else None

    async def create_worker(
        self,
        *,
        organization_id: uuid.UUID,
        name: str,
        trade: str | None,
        worker_type: str,
        default_daily_wage: float | None,
        contractor: str | None,
        status: str,
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        worker_id = uuid.uuid4()
        await self._conn.execute(
            _workforce_workers.insert().values(
                id=worker_id,
                organization_id=organization_id,
                name=name,
                trade=trade,
                worker_type=worker_type,
                default_daily_wage=default_daily_wage,
                contractor=contractor,
                status=status,
                created_at=sa.func.now(),
                created_by=created_by,
                updated_at=sa.func.now(),
                updated_by=created_by,
            )
        )
        worker = await self.get_worker(organization_id, worker_id)
        assert worker is not None
        return worker

    async def update_worker(
        self,
        *,
        organization_id: uuid.UUID,
        worker_id: uuid.UUID,
        patch: dict[str, Any],
        updated_by: uuid.UUID,
    ) -> dict[str, Any] | None:
        if not patch:
            return await self.get_worker(organization_id, worker_id)
        await self._conn.execute(
            _workforce_workers.update()
            .where(
                _workforce_workers.c.organization_id == organization_id,
                _workforce_workers.c.id == worker_id,
            )
            .values(**patch, updated_at=sa.func.now(), updated_by=updated_by)
        )
        return await self.get_worker(organization_id, worker_id)

    # --- Attendance reports (read-only; writes go through labour_execution.py) -

    async def list_reports(
        self,
        *,
        organization_id: uuid.UUID,
        project_ids: set[uuid.UUID] | None,
        site_id: uuid.UUID | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions = [_labour_attendance_reports.c.organization_id == organization_id]
        if project_ids is not None:
            conditions.append(_labour_attendance_reports.c.project_id.in_(project_ids))
        if site_id is not None:
            conditions.append(_labour_attendance_reports.c.site_id == site_id)
        if date_from is not None:
            conditions.append(_labour_attendance_reports.c.occurred_date >= date_from)
        if date_to is not None:
            conditions.append(_labour_attendance_reports.c.occurred_date <= date_to)

        total = (
            await self._conn.execute(
                sa.select(sa.func.count())
                .select_from(_labour_attendance_reports)
                .where(*conditions)
            )
        ).scalar_one()

        report_rows = (
            await self._conn.execute(
                sa.select(_labour_attendance_reports)
                .where(*conditions)
                .order_by(_labour_attendance_reports.c.occurred_date.desc())
                .limit(limit)
                .offset(offset)
            )
        ).mappings().all()

        items: list[dict[str, Any]] = []
        for report in report_rows:
            line_rows = (
                await self._conn.execute(
                    sa.select(_labour_attendance_lines).where(
                        _labour_attendance_lines.c.report_id == report["id"]
                    )
                )
            ).mappings().all()
            lines = [dict(line) for line in line_rows]
            headcount, cost = _line_totals(lines)
            items.append(
                {
                    **dict(report),
                    "line_count": len(lines),
                    "total_headcount": headcount,
                    "total_cost": cost,
                }
            )
        return items, int(total)

    async def get_report(
        self, organization_id: uuid.UUID, report_id: uuid.UUID
    ) -> dict[str, Any] | None:
        report = (
            await self._conn.execute(
                sa.select(_labour_attendance_reports).where(
                    _labour_attendance_reports.c.organization_id == organization_id,
                    _labour_attendance_reports.c.id == report_id,
                )
            )
        ).mappings().first()
        if report is None:
            return None

        line_rows = (
            await self._conn.execute(
                sa.select(_labour_attendance_lines).where(
                    _labour_attendance_lines.c.report_id == report_id
                )
            )
        ).mappings().all()
        lines = [dict(line) for line in line_rows]

        attachment_rows = (
            await self._conn.execute(
                sa.select(_labour_attendance_attachments).where(
                    _labour_attendance_attachments.c.report_id == report_id
                )
            )
        ).mappings().all()

        headcount, cost = _line_totals(lines)
        return {
            **dict(report),
            "lines": lines,
            "attachments": [dict(a) for a in attachment_rows],
            "total_headcount": headcount,
            "total_cost": cost,
        }
