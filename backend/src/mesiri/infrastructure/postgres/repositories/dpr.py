"""PostgreSQL repository for Daily Progress Reports (DPR).

Handles read/write operations for daily_reports, daily_report_versions, and
daily_report_sources (docs/execution/DAILY_REPORTING_PLAN.md ADR-D6/D9).

`assemble_site_report_payload` + `create_version` are the real generation
path (#16 Daily Report Generation): they compose a version's `payload`
JSONB from the activities/site_issues/progress_attachments actually
recorded for one site+date, rather than trusting a caller-supplied payload.
The older `create_report`/`get_report`/`list_reports` methods remain for the
existing dashboard's manual-entry form (POST /dpr/daily-reports with a
hand-typed payload) -- a different, still-valid path for a report with no
WhatsApp activity behind it, not something this generation path replaces.

Scope, stated plainly (matches this session's other narrowing decisions):
`assemble_site_report_payload` composes activities + site_issues +
evidence *counts* for one SITE-level report. It does NOT pull in
labour/equipment/expense records from their own modules -- that needs a
cross-module read this repository has no business making on its own
(#22 Cross-Module Trigger territory), and PROJECT-level composition from
approved SITE versions (ADR-D9/P8, `daily_report_sources`) is not built
here either. Both are natural next steps, not silently done halfway.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


class PostgresDprRepository:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # Manual-entry path (existing dashboard form) -- unchanged in shape,
    # only the enum bug below is fixed.
    # ------------------------------------------------------------------

    async def list_reports(
        self,
        *,
        organization_id: uuid.UUID,
        project_ids: set[uuid.UUID] | None,
        site_id: uuid.UUID | None,
        status: str | None,
        date_from: datetime.date | None,
        date_to: datetime.date | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["dr.organization_id = :organization_id"]
        params: dict[str, Any] = {"organization_id": organization_id, "limit": limit, "offset": offset}

        if project_ids is not None:
            where.append("dr.project_id = ANY(:project_ids)")
            params["project_ids"] = list(project_ids)
        if site_id is not None:
            where.append("dr.site_id = :site_id")
            params["site_id"] = site_id
        if date_from is not None:
            where.append("dr.report_date >= :date_from")
            params["date_from"] = date_from
        if date_to is not None:
            where.append("dr.report_date <= :date_to")
            params["date_to"] = date_to
        if status is not None:
            where.append("dr.status = :status")
            params["status"] = status.upper()

        where_clause = " AND ".join(where)

        total_row = (
            await self._conn.execute(
                text(f"SELECT COUNT(*) AS total FROM daily_reports dr WHERE {where_clause}"), params
            )
        ).mappings().first()
        total = total_row["total"] if total_row else 0

        query = f"""
            SELECT
                dr.id,
                COALESCE(dr.code, concat('DPR-', to_char(dr.report_date, 'YYYYMMDD'), '-', SUBSTRING(dr.id::text, 1, 4))) AS dpr_number,
                dr.report_date::text AS report_date,
                p.name AS project_name,
                COALESCE(s.name, 'Project-wide') AS site_name,
                COALESCE(u.name, 'Site Lead') AS prepared_by_name,
                'Site Engineer' AS prepared_by_role,
                LOWER(dr.status::text) AS workflow_status,
                'sunny' AS weather,
                32 AS temperature_celsius,
                'day' AS shift,
                0 AS activities_count,
                0 AS labour_count,
                0 AS issues_count,
                '' AS narrative_summary,
                dr.created_at::text AS created_at
            FROM daily_reports dr
            JOIN projects p ON dr.project_id = p.id
            LEFT JOIN sites s ON dr.site_id = s.id
            LEFT JOIN users u ON p.organization_id = u.organization_id
            WHERE {where_clause}
            ORDER BY dr.report_date DESC, dr.created_at DESC
            LIMIT :limit OFFSET :offset
        """

        rows = (await self._conn.execute(text(query), params)).mappings().all()
        return [dict(r) for r in rows], total

    async def get_report(
        self, organization_id: uuid.UUID, report_id: uuid.UUID
    ) -> dict[str, Any] | None:
        query = """
            SELECT
                dr.id,
                COALESCE(dr.code, concat('DPR-', to_char(dr.report_date, 'YYYYMMDD'), '-', SUBSTRING(dr.id::text, 1, 4))) AS dpr_number,
                dr.report_date::text AS report_date,
                p.name AS project_name,
                COALESCE(s.name, 'Project-wide') AS site_name,
                'Site Engineer' AS prepared_by_name,
                'Site Lead' AS prepared_by_role,
                LOWER(dr.status::text) AS workflow_status,
                'sunny' AS weather,
                32 AS temperature_celsius,
                'day' AS shift,
                0 AS activities_count,
                0 AS labour_count,
                0 AS issues_count,
                '' AS narrative_summary,
                dr.created_at::text AS created_at,
                '[]'::json AS work_items,
                '[]'::json AS labour_items,
                '[]'::json AS equipment_items,
                '[]'::json AS issues,
                '[]'::json AS attachments
            FROM daily_reports dr
            JOIN projects p ON dr.project_id = p.id
            LEFT JOIN sites s ON dr.site_id = s.id
            WHERE dr.organization_id = :org_id AND dr.id = :id
        """
        row = (await self._conn.execute(text(query), {"org_id": organization_id, "id": report_id})).mappings().first()
        return dict(row) if row else None

    async def create_report(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, payload: dict[str, Any]
    ) -> dict[str, Any]:
        report_id = uuid.uuid4()
        report_date = payload["report_date"]
        project_id = payload.get("project_id")
        site_id = payload.get("site_id")

        if not project_id:
            # Fallback to first project in organization
            first_p = (await self._conn.execute(
                text("SELECT id FROM projects WHERE organization_id = :org_id LIMIT 1"),
                {"org_id": organization_id}
            )).mappings().first()
            project_id = first_p["id"] if first_p else uuid.uuid4()

        code = f"DPR-{report_date.replace('-', '')}-{str(report_id)[:4].upper()}"

        query = """
            INSERT INTO daily_reports (
                id, organization_id, project_id, site_id, level, report_date, code, status
            ) VALUES (
                :id, :organization_id, :project_id, :site_id, :level, :report_date, :code, 'DRAFT'
            ) RETURNING id, code, report_date::text AS report_date, status::text AS workflow_status
        """
        # Status is 'DRAFT' -- daily_report_status's actual enum values are
        # DRAFT/IN_REVIEW/APPROVED/PUBLISHED/NOT_REPORTED (migration 0440).
        # This previously inserted 'UNDER_REVIEW', which isn't a member of
        # that enum -- a live INSERT would have raised
        # InvalidTextRepresentation the first time this code path actually
        # ran against Postgres. Caught while building the real generation
        # path below, before this manual-entry path had ever been exercised
        # against a live database (0440's own docstring: "No application
        # code writes to these tables yet").
        params = {
            "id": report_id,
            "organization_id": organization_id,
            "project_id": project_id,
            "site_id": site_id,
            "level": "SITE" if site_id else "PROJECT",
            "report_date": report_date,
            "code": code,
        }
        res = (await self._conn.execute(text(query), params)).mappings().first()
        res_dict = dict(res)
        res_dict["dpr_number"] = res_dict["code"]
        res_dict["workflow_status"] = res_dict["workflow_status"].lower()
        res_dict["project_name"] = "Active Project"
        res_dict["site_name"] = "Active Site"
        res_dict["prepared_by_name"] = "Current Engineer"
        res_dict["weather"] = payload.get("weather", "sunny")
        res_dict["temperature_celsius"] = payload.get("temperature_celsius", 32)
        res_dict["shift"] = payload.get("shift", "day")
        res_dict["activities_count"] = len(payload.get("work_items", []))
        res_dict["labour_count"] = sum(item.get("headcount", 0) for item in payload.get("labour_items", []))
        res_dict["issues_count"] = len(payload.get("issues", []))

        return res_dict

    async def submit_for_review(
        self, organization_id: uuid.UUID, report_id: uuid.UUID
    ) -> bool:
        """DRAFT -> IN_REVIEW. The step a manually-created report was
        missing entirely: without it, a report sat in DRAFT forever since
        approve_report only ever fired from the (unreachable) 'in_review'
        state the dashboard's detail view checks for."""
        query = """
            UPDATE daily_reports
            SET status = 'IN_REVIEW', updated_at = now()
            WHERE organization_id = :org_id AND id = :id AND status = 'DRAFT'
        """
        res = await self._conn.execute(text(query), {"org_id": organization_id, "id": report_id})
        return res.rowcount > 0

    async def approve_report(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, report_id: uuid.UUID, notes: str | None
    ) -> bool:
        # Accepts DRAFT or IN_REVIEW -> APPROVED. Kept permissive (not
        # restricted to IN_REVIEW only) so the existing bulk-approve action,
        # which never calls submit_for_review first, keeps working.
        query = """
            UPDATE daily_reports
            SET status = 'APPROVED', updated_at = now()
            WHERE organization_id = :org_id AND id = :id AND status IN ('DRAFT', 'IN_REVIEW')
        """
        res = await self._conn.execute(text(query), {"org_id": organization_id, "id": report_id})
        return res.rowcount > 0

    async def publish_report(
        self, organization_id: uuid.UUID, report_id: uuid.UUID
    ) -> bool:
        """APPROVED -> PUBLISHED. Terminal per P7 (create_version already
        refuses to regenerate a payload once status is APPROVED/PUBLISHED);
        this is the explicit sign-off action the dashboard's 'Frozen &
        Signed' badge described but nothing ever set."""
        query = """
            UPDATE daily_reports
            SET status = 'PUBLISHED', updated_at = now()
            WHERE organization_id = :org_id AND id = :id AND status = 'APPROVED'
        """
        res = await self._conn.execute(text(query), {"org_id": organization_id, "id": report_id})
        return res.rowcount > 0

    # ------------------------------------------------------------------
    # Real generation path (#16 Daily Report Generation).
    # ------------------------------------------------------------------

    async def assemble_site_report_payload(
        self,
        *,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        report_date: datetime.date,
    ) -> dict[str, Any]:
        """Compose one SITE-level DPR payload from what was actually
        recorded on `report_date` -- activities (with their quantities),
        open+resolved-today site issues, and an evidence count per
        activity. Returns a plain JSON-safe dict, ready for
        `create_version`'s `payload` column or a PDF renderer.

        Photo bytes are NOT embedded here -- only counts and captions.
        Inlining actual thumbnails needs the object-storage read wired
        through this call, deferred to keep this pass to counts/text
        (see module docstring's scope note).
        """
        header_query = text(
            """
            SELECT
                (SELECT name FROM projects WHERE id = :project_id) AS project_name,
                (SELECT name FROM sites WHERE id = :site_id) AS site_name
            """
        )
        header = (
            await self._conn.execute(
                header_query, {"project_id": project_id, "site_id": site_id}
            )
        ).mappings().first()

        activities_query = text(
            """
            SELECT a.id, a.work_type, a.narrative, a.status, a.contractor,
                   a.started_at, a.ended_at
            FROM activities a
            WHERE a.organization_id = :org_id
              AND a.project_id = :project_id
              AND a.site_id = :site_id
              AND a.activity_date = :report_date
              AND a.deleted_at IS NULL
            ORDER BY a.created_at
            """
        )
        activity_rows = (
            await self._conn.execute(
                activities_query,
                {
                    "org_id": organization_id,
                    "project_id": project_id,
                    "site_id": site_id,
                    "report_date": report_date,
                },
            )
        ).mappings().all()

        activity_ids = [row["id"] for row in activity_rows]

        quantities_by_activity: dict[Any, list[dict[str, Any]]] = {}
        evidence_count_by_activity: dict[Any, int] = {}
        if activity_ids:
            quantities_query = text(
                """
                SELECT aq.activity_id, aq.work_type, aq.quantity, u.code AS unit_code
                FROM activity_quantities aq
                JOIN units_of_measure u ON u.id = aq.unit_id
                WHERE aq.activity_id = ANY(:activity_ids)
                ORDER BY aq.created_at
                """
            )
            for row in (
                await self._conn.execute(quantities_query, {"activity_ids": activity_ids})
            ).mappings().all():
                quantities_by_activity.setdefault(row["activity_id"], []).append(
                    {
                        "work_type": row["work_type"],
                        "quantity": str(row["quantity"]),
                        "unit": row["unit_code"],
                    }
                )

            evidence_query = text(
                """
                SELECT parent_id AS activity_id, count(*) AS n
                FROM progress_attachments
                WHERE parent_type = 'ACTIVITY' AND parent_id = ANY(:activity_ids)
                GROUP BY parent_id
                """
            )
            for row in (
                await self._conn.execute(evidence_query, {"activity_ids": activity_ids})
            ).mappings().all():
                evidence_count_by_activity[row["activity_id"]] = int(row["n"])

        issues_query = text(
            """
            SELECT issue_type, severity, narrative, status, delay_duration_minutes
            FROM site_issues
            WHERE organization_id = :org_id
              AND project_id = :project_id
              AND site_id = :site_id
              AND occurred_at::date = :report_date
            ORDER BY
                CASE severity WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1
                              WHEN 'MEDIUM' THEN 2 ELSE 3 END,
                occurred_at
            """
        )
        issue_rows = (
            await self._conn.execute(
                issues_query,
                {
                    "org_id": organization_id,
                    "project_id": project_id,
                    "site_id": site_id,
                    "report_date": report_date,
                },
            )
        ).mappings().all()

        from mesiri.application.dpr.assembly import build_site_report_payload

        return build_site_report_payload(
            project_name=header["project_name"] if header else None,
            site_name=header["site_name"] if header else None,
            report_date=report_date,
            activity_rows=[dict(row) for row in activity_rows],
            quantities_by_activity=quantities_by_activity,
            evidence_count_by_activity=evidence_count_by_activity,
            issue_rows=[dict(row) for row in issue_rows],
        )

    async def get_or_create_daily_report(
        self,
        *,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        site_id: uuid.UUID,
        report_date: datetime.date,
    ) -> uuid.UUID:
        """The `daily_reports` row for this SITE+date, creating it (status
        DRAFT) if this is the first version ever generated for it. Never
        creates a second row for the same scope+date -- `uq_daily_report_
        scope_date` is the authority, this just upserts against it."""
        existing = (
            await self._conn.execute(
                text(
                    """
                    SELECT id FROM daily_reports
                    WHERE organization_id = :org_id AND project_id = :project_id
                      AND site_id = :site_id AND report_date = :report_date AND level = 'SITE'
                    """
                ),
                {
                    "org_id": organization_id,
                    "project_id": project_id,
                    "site_id": site_id,
                    "report_date": report_date,
                },
            )
        ).mappings().first()
        if existing:
            return existing["id"]

        report_id = uuid.uuid4()
        code = f"DPR-{report_date.strftime('%Y%m%d')}-{str(report_id)[:4].upper()}"
        await self._conn.execute(
            text(
                """
                INSERT INTO daily_reports (
                    id, organization_id, project_id, site_id, level, report_date, code, status
                ) VALUES (
                    :id, :org_id, :project_id, :site_id, 'SITE', :report_date, :code, 'DRAFT'
                )
                """
            ),
            {
                "id": report_id,
                "org_id": organization_id,
                "project_id": project_id,
                "site_id": site_id,
                "report_date": report_date,
                "code": code,
            },
        )
        return report_id

    async def create_version(
        self,
        *,
        daily_report_id: uuid.UUID,
        payload: dict[str, Any],
        narrative_summary: str | None = None,
    ) -> dict[str, Any]:
        """Insert a new version (P7: never mutate a prior version's
        payload) and point `daily_reports.current_version_id` at it. A
        report already APPROVED/PUBLISHED is left alone -- regenerating a
        frozen day's DRAFT payload after approval would defeat the freeze
        this table exists to enforce; callers that need to correct an
        approved day must go through a revision with `revision_reason`,
        not this happy-path insert (not built here -- see module docstring)."""
        report_row = (
            await self._conn.execute(
                text("SELECT status FROM daily_reports WHERE id = :id"),
                {"id": daily_report_id},
            )
        ).mappings().first()
        if report_row and report_row["status"] in ("APPROVED", "PUBLISHED"):
            raise ValueError(
                f"daily_report {daily_report_id} is already {report_row['status']} -- "
                "cannot silently overwrite an approved version's payload"
            )

        next_version_row = (
            await self._conn.execute(
                text(
                    "SELECT COALESCE(MAX(version_no), 0) + 1 AS next FROM daily_report_versions "
                    "WHERE daily_report_id = :id"
                ),
                {"id": daily_report_id},
            )
        ).mappings().first()
        version_no = next_version_row["next"]

        version_id = uuid.uuid4()
        import json

        await self._conn.execute(
            text(
                """
                INSERT INTO daily_report_versions (
                    id, daily_report_id, version_no, payload, narrative_summary
                ) VALUES (
                    :id, :daily_report_id, :version_no, CAST(:payload AS JSONB), :narrative_summary
                )
                """
            ),
            {
                "id": version_id,
                "daily_report_id": daily_report_id,
                "version_no": version_no,
                "payload": json.dumps(payload),
                "narrative_summary": narrative_summary,
            },
        )
        await self._conn.execute(
            text(
                "UPDATE daily_reports SET current_version_id = :version_id, "
                "status = 'DRAFT', updated_at = now() WHERE id = :id"
            ),
            {"version_id": version_id, "id": daily_report_id},
        )
        return {"id": version_id, "daily_report_id": daily_report_id, "version_no": version_no}

    async def get_report_for_pdf(
        self, *, organization_id: uuid.UUID, report_id: uuid.UUID
    ) -> dict[str, Any] | None:
        """Everything a PDF export needs for one report: its current
        version's `payload` (the same JSON the assistant-side Playwright
        renderer already consumes, see application/dpr/assembly.py) plus
        whatever `rendered_object_key` that version already has, if the
        nightly cron (runtime/render_pending_dpr_pdfs.py) got to it first.

        Returns None for a report with no `current_version_id` at all --
        i.e. one created through the manual-entry form (create_report),
        which never gets a payload/version row. There is nothing real to
        render for those; the router surfaces that as a 404 rather than
        fabricating a PDF from fields that don't exist.
        """
        row = (
            await self._conn.execute(
                text(
                    """
                    SELECT
                        dr.id, dr.code, dr.report_date::text AS report_date,
                        dr.status::text AS workflow_status,
                        p.name AS project_name,
                        s.name AS site_name,
                        v.id AS version_id, v.payload, v.rendered_object_key
                    FROM daily_reports dr
                    JOIN projects p ON p.id = dr.project_id
                    LEFT JOIN sites s ON s.id = dr.site_id
                    LEFT JOIN daily_report_versions v ON v.id = dr.current_version_id
                    WHERE dr.organization_id = :org_id AND dr.id = :id
                    """
                ),
                {"org_id": organization_id, "id": report_id},
            )
        ).mappings().first()
        if row is None or row["version_id"] is None:
            return None
        return dict(row)

    async def set_rendered_object_key(self, *, version_id: uuid.UUID, object_key: str) -> None:
        await self._conn.execute(
            text(
                "UPDATE daily_report_versions SET rendered_object_key = :key WHERE id = :id"
            ),
            {"key": object_key, "id": version_id},
        )

    async def list_unrendered_versions(self, *, limit: int = 20) -> list[dict[str, Any]]:
        """Versions with a payload but no PDF yet -- what the assistant-side
        render script (runtime/render_pending_dpr_pdfs.py) drains. Crosses
        the same backend/assistant boundary #9 Notifications' queue does:
        this repository (backend) only ever writes rows and the object key
        column; rendering itself needs Playwright, which lives on the
        assistant side (ADR-D8 -- reuses channel/receipt/'s pipeline)."""
        rows = (
            await self._conn.execute(
                text(
                    """
                    SELECT v.id AS version_id, v.daily_report_id, v.payload,
                           dr.code, dr.report_date::text AS report_date
                    FROM daily_report_versions v
                    JOIN daily_reports dr ON dr.id = v.daily_report_id
                    WHERE v.rendered_object_key IS NULL
                    ORDER BY v.created_at
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
        ).mappings().all()
        return [dict(r) for r in rows]
