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
import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

# site_issue_type / site_issue_status enum members (migration 0430) — kept
# here rather than in domains/progress/validation.py because that file only
# validates the WhatsApp-confirmed command path (CreateActivityCommand /
# AddProgressUpdateCommand); Site Issues are written directly by this
# dashboard-facing REST path (no confirm step), so their own validation lives
# next to the SQL it guards.
VALID_ISSUE_TYPES = frozenset(
    {
        "WEATHER",
        "MATERIAL_SHORTAGE",
        "LABOUR_SHORTAGE",
        "DRAWING_PENDING",
        "EQUIPMENT_BREAKDOWN",
        "INSPECTION_WAITING",
        "ACCESS",
        "OTHER",
    }
)
VALID_ISSUE_SEVERITIES = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})


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

    async def list_issues(
        self,
        *,
        organization_id: uuid.UUID,
        project_ids: set[uuid.UUID] | None,
        site_id: uuid.UUID | None,
        status: str | None,
        severity: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["organization_id = :organization_id"]
        params: dict[str, Any] = {"organization_id": organization_id, "limit": limit, "offset": offset}

        if project_ids is not None:
            where.append("project_id = ANY(:project_ids)")
            params["project_ids"] = list(project_ids)
        if site_id is not None:
            where.append("site_id = :site_id")
            params["site_id"] = site_id
        if status is not None:
            where.append("status = :status")
            params["status"] = status
        if severity is not None:
            where.append("severity = :severity")
            params["severity"] = severity

        where_clause = " AND ".join(where)

        total_row = (
            await self._conn.execute(
                text(f"SELECT COUNT(*) AS total FROM site_issues WHERE {where_clause}"), params
            )
        ).mappings().first()
        total = total_row["total"] if total_row else 0

        rows = (
            await self._conn.execute(
                text(
                    f"SELECT id, organization_id, project_id, site_id, activity_id, "
                    f"work_package_id, location_id, issue_type, severity, narrative, "
                    f"delay_duration_minutes, occurred_at, resolved_at, status, "
                    f"resolution_notes, assigned_user_id, reported_by_user_id, "
                    f"created_at, updated_at "
                    f"FROM site_issues WHERE {where_clause} "
                    f"ORDER BY occurred_at DESC LIMIT :limit OFFSET :offset"
                ),
                params,
            )
        ).mappings().all()
        return [dict(row) for row in rows], total

    async def get_issue(
        self, organization_id: uuid.UUID, issue_id: uuid.UUID
    ) -> dict[str, Any] | None:
        row = (
            (
                await self._conn.execute(
                    text(
                        "SELECT id, organization_id, project_id, site_id, activity_id, "
                        "work_package_id, location_id, issue_type, severity, narrative, "
                        "delay_duration_minutes, occurred_at, resolved_at, status, "
                        "resolution_notes, assigned_user_id, reported_by_user_id, "
                        "created_at, updated_at "
                        "FROM site_issues WHERE organization_id = :org_id AND id = :id"
                    ),
                    {"org_id": organization_id, "id": issue_id},
                )
            )
            .mappings()
            .first()
        )
        return dict(row) if row is not None else None

    async def _emit_issue_event(
        self,
        *,
        issue_id: uuid.UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """INSERT one outbox_events row for a Site Issue lifecycle change,
        the same generic mechanism progress_execution.py uses for
        Activity/Progress Update events. Site Issues have no confirm step
        (dashboard-only, no WhatsApp draft), so there is no
        idempotency_key/correlation_id here — just a plain fact for
        timeline_projector.py to pick up (registered as aggregate_type
        'site_issue' in AGGREGATE_TABLES)."""
        await self._conn.execute(
            text(
                "INSERT INTO outbox_events "
                "(id, aggregate_type, aggregate_id, event_type, payload) "
                "VALUES (:id, 'site_issue', :aggregate_id, :event_type, CAST(:payload AS jsonb))"
            ),
            {
                "id": uuid.uuid4(),
                "aggregate_id": issue_id,
                "event_type": event_type,
                "payload": json.dumps(payload, default=str),
            },
        )

    async def create_issue(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, payload: dict[str, Any]
    ) -> dict[str, Any]:
        issue_id = uuid.uuid4()
        now = datetime.datetime.now(datetime.UTC)
        issue_type = payload.get("issue_type") or "OTHER"
        severity = payload.get("severity") or "MEDIUM"
        if issue_type not in VALID_ISSUE_TYPES:
            raise ValueError(f"invalid issue_type: {issue_type}")
        if severity not in VALID_ISSUE_SEVERITIES:
            raise ValueError(f"invalid severity: {severity}")

        query = """
            INSERT INTO site_issues (
                id, organization_id, project_id, site_id, activity_id, work_package_id,
                location_id, issue_type, severity, narrative, delay_duration_minutes,
                occurred_at, status, assigned_user_id, reported_by_user_id, created_at, updated_at
            ) VALUES (
                :id, :organization_id, :project_id, :site_id, :activity_id, :work_package_id,
                :location_id, :issue_type, :severity, :narrative, :delay_duration_minutes,
                :occurred_at, 'OPEN', :assigned_user_id, :reported_by_user_id, :now, :now
            ) RETURNING id, organization_id, project_id, site_id, activity_id,
                        work_package_id, location_id, issue_type, severity, narrative,
                        delay_duration_minutes, occurred_at, resolved_at, status,
                        resolution_notes, assigned_user_id, reported_by_user_id,
                        created_at, updated_at
        """
        params = {
            "id": issue_id,
            "organization_id": organization_id,
            "project_id": payload["project_id"],
            "site_id": payload["site_id"],
            "activity_id": payload.get("activity_id"),
            "work_package_id": payload.get("work_package_id"),
            "location_id": payload.get("location_id"),
            "issue_type": issue_type,
            "severity": severity,
            "narrative": payload.get("narrative"),
            "delay_duration_minutes": payload.get("delay_duration_minutes"),
            "occurred_at": now,
            "assigned_user_id": payload.get("assigned_user_id"),
            "reported_by_user_id": user_id,
            "now": now,
        }
        res = (await self._conn.execute(text(query), params)).mappings().first()
        result = dict(res)

        await self._emit_issue_event(
            issue_id=issue_id,
            event_type="SiteIssueReported",
            payload={
                "issue_type": issue_type,
                "severity": severity,
                "narrative": payload.get("narrative"),
                "delay_duration_minutes": payload.get("delay_duration_minutes"),
            },
        )
        return result

    async def acknowledge_issue(
        self, organization_id: uuid.UUID, issue_id: uuid.UUID
    ) -> bool:
        """OPEN -> ACKNOWLEDGED only. Mirrors resolve_issue's shape but
        narrower: acknowledging an already-ACKNOWLEDGED/RESOLVED/WONT_FIX
        issue is a no-op (returns False), same as re-resolving one does."""
        now = datetime.datetime.now(datetime.UTC)
        query = """
            UPDATE site_issues
            SET status = 'ACKNOWLEDGED', updated_at = :now
            WHERE organization_id = :org_id AND id = :id AND status = 'OPEN'
        """
        res = await self._conn.execute(text(query), {"org_id": organization_id, "id": issue_id, "now": now})
        if res.rowcount > 0:
            await self._emit_issue_event(issue_id=issue_id, event_type="SiteIssueAcknowledged", payload={})
        return res.rowcount > 0

    async def wont_fix_issue(
        self, organization_id: uuid.UUID, issue_id: uuid.UUID, notes: str | None
    ) -> bool:
        """OPEN/ACKNOWLEDGED -> WONT_FIX. Terminal, like RESOLVED — a
        WONT_FIX issue is not later resolved or reopened; if the underlying
        problem turns out to matter after all, that's a new site issue."""
        now = datetime.datetime.now(datetime.UTC)
        query = """
            UPDATE site_issues
            SET status = 'WONT_FIX', resolved_at = :now, resolution_notes = :notes, updated_at = :now
            WHERE organization_id = :org_id AND id = :id AND status IN ('OPEN', 'ACKNOWLEDGED')
        """
        res = await self._conn.execute(
            text(query), {"org_id": organization_id, "id": issue_id, "notes": notes, "now": now}
        )
        if res.rowcount > 0:
            await self._emit_issue_event(
                issue_id=issue_id, event_type="SiteIssueWontFix", payload={"resolution_notes": notes}
            )
        return res.rowcount > 0

    async def resolve_issue(
        self, organization_id: uuid.UUID, issue_id: uuid.UUID, notes: str | None
    ) -> bool:
        now = datetime.datetime.now(datetime.UTC)
        query = """
            UPDATE site_issues
            SET status = 'RESOLVED', resolved_at = :now, resolution_notes = :notes, updated_at = :now
            WHERE organization_id = :org_id AND id = :id AND status != 'RESOLVED'
        """
        res = await self._conn.execute(text(query), {"org_id": organization_id, "id": issue_id, "notes": notes, "now": now})
        if res.rowcount > 0:
            await self._emit_issue_event(
                issue_id=issue_id, event_type="SiteIssueResolved", payload={"resolution_notes": notes}
            )
        return res.rowcount > 0

