"""Read access for activities, progress updates, and site issues.

Companion to progress_execution.py, which owns the *write* path a WhatsApp
confirmation takes. This file is the dashboard-facing read side only —
Activities and Progress Updates are operational records like Labour
attendance, never written directly by the dashboard (plan P2: nothing is
persisted before an explicit confirmation), so there is no create/update
method here, only reads. Mirrors workforce.py's read/write split.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


class PostgresProgressReadRepository:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def list_activities(
        self,
        *,
        organization_id: uuid.UUID,
        project_ids: set[uuid.UUID] | None,
        site_id: uuid.UUID | None,
        date_from: datetime.date | None,
        date_to: datetime.date | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["organization_id = :organization_id", "deleted_at IS NULL"]
        params: dict[str, Any] = {"organization_id": organization_id, "limit": limit, "offset": offset}

        if project_ids is not None:
            where.append("project_id = ANY(:project_ids)")
            params["project_ids"] = list(project_ids)
        if site_id is not None:
            where.append("site_id = :site_id")
            params["site_id"] = site_id
        if date_from is not None:
            where.append("activity_date >= :date_from")
            params["date_from"] = date_from
        if date_to is not None:
            where.append("activity_date <= :date_to")
            params["date_to"] = date_to
        if status is not None:
            where.append("status = :status")
            params["status"] = status

        where_clause = " AND ".join(where)

        total_row = (
            await self._conn.execute(
                text(f"SELECT COUNT(*) AS total FROM activities WHERE {where_clause}"), params
            )
        ).mappings().first()
        total = total_row["total"] if total_row else 0

        rows = (
            await self._conn.execute(
                text(
                    f"SELECT id, organization_id, project_id, site_id, work_package_id, "
                    f"location_id, work_type, activity_date, started_at, ended_at, status, "
                    f"narrative, contractor, reported_by_user_id, source, created_at, updated_at "
                    f"FROM activities WHERE {where_clause} "
                    f"ORDER BY activity_date DESC, created_at DESC LIMIT :limit OFFSET :offset"
                ),
                params,
            )
        ).mappings().all()
        return [dict(row) for row in rows], total

    async def get_activity(
        self, organization_id: uuid.UUID, activity_id: uuid.UUID
    ) -> dict[str, Any] | None:
        row = (
            (
                await self._conn.execute(
                    text(
                        "SELECT id, organization_id, project_id, site_id, work_package_id, "
                        "location_id, work_type, activity_date, started_at, ended_at, status, "
                        "narrative, contractor, reported_by_user_id, source, created_at, updated_at "
                        "FROM activities WHERE organization_id = :org_id AND id = :id "
                        "AND deleted_at IS NULL"
                    ),
                    {"org_id": organization_id, "id": activity_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return None

        item = dict(row)

        quantities = (
            (
                await self._conn.execute(
                    text(
                        "SELECT aq.id, aq.work_type, aq.unit_id, u.code AS unit, aq.quantity, "
                        "aq.measurement_type "
                        "FROM activity_quantities aq "
                        "LEFT JOIN units_of_measure u ON u.id = aq.unit_id "
                        "WHERE aq.activity_id = :activity_id ORDER BY aq.created_at ASC"
                    ),
                    {"activity_id": activity_id},
                )
            )
            .mappings()
            .all()
        )
        item["quantities"] = [dict(q) for q in quantities]

        updates = (
            (
                await self._conn.execute(
                    text(
                        "SELECT pu.id, pu.occurred_at, pu.update_kind, pu.narrative, pu.quantity, "
                        "pu.unit_id, u.code AS unit, pu.reported_by_user_id, pu.source, pu.created_at "
                        "FROM progress_updates pu "
                        "LEFT JOIN units_of_measure u ON u.id = pu.unit_id "
                        "WHERE pu.activity_id = :activity_id AND pu.deleted_at IS NULL "
                        "ORDER BY pu.occurred_at ASC"
                    ),
                    {"activity_id": activity_id},
                )
            )
            .mappings()
            .all()
        )
        item["progress_updates"] = [dict(u) for u in updates]

        attachments = (
            (
                await self._conn.execute(
                    text(
                        "SELECT id, media_object_key, attachment_type, mime_type, caption, "
                        "ai_caption, role, captured_at, created_at "
                        "FROM progress_attachments "
                        "WHERE parent_type = 'ACTIVITY' AND parent_id = :activity_id "
                        "ORDER BY created_at ASC"
                    ),
                    {"activity_id": activity_id},
                )
            )
            .mappings()
            .all()
        )
        item["attachments"] = [dict(a) for a in attachments]

        return item
