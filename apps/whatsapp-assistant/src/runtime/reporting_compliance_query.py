"""Reporting-compliance read service for the COMPLIANCE_SUMMARY automation
action ("at 3pm tell me who hasn't reported") and the NON_REPORTERS audience.

"Reported" means the same thing run_dpr_generation.py's own
`_sites_with_activity` already uses to decide which sites get a DPR draft
at all: at least one `activities` row or `site_issues` row for that
project/site on the target date. Not `daily_reports.status` -- a site can
report and simply not have had its DPR approved yet, and "did anyone log
anything today" is the question a 3pm compliance check actually asks, not
"is today's paperwork signed off."

Read-only: never opens a write transaction, never mutates state. Callable
headlessly (no inbound message, no ActorIdentity) with just
(organization_id, project_id) -- the automation runner has no message to
resolve context from.
"""

from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mesiri.infrastructure.postgres.database import PostgresDatabase


class ReportingComplianceQueryService:
    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    async def check(
        self,
        *,
        organization_id: str,
        project_id: str | None,
        report_date: datetime.date,
    ) -> dict[str, Any]:
        """Every active site in scope (all of the org's if `project_id` is
        None, one project's otherwise), split into reported/not-reported
        for `report_date`. Returns a plain dict: `sites` (each
        {"site_id","site_name","reported"}), `reported_count`,
        `not_reported_count`."""
        import sqlalchemy as sa

        async with self._db.transaction() as conn:
            org_uuid = uuid.UUID(organization_id)
            site_where = ["organization_id = :org_id", "status = 'active'"]
            params: dict[str, Any] = {"org_id": org_uuid}
            if project_id:
                site_where.append("project_id = :project_id")
                params["project_id"] = uuid.UUID(project_id)

            site_rows = (
                await conn.execute(
                    sa.text(
                        f"SELECT id, name, project_id FROM sites WHERE {' AND '.join(site_where)} "
                        "ORDER BY name"
                    ),
                    params,
                )
            ).mappings().all()
            site_ids = [row["id"] for row in site_rows]

            reported_site_ids: set[uuid.UUID] = set()
            if site_ids:
                reported_rows = (
                    await conn.execute(
                        sa.text(
                            """
                            SELECT DISTINCT site_id FROM activities
                            WHERE organization_id = :org_id AND activity_date = :report_date
                              AND site_id = ANY(:site_ids) AND deleted_at IS NULL
                            UNION
                            SELECT DISTINCT site_id FROM site_issues
                            WHERE organization_id = :org_id AND occurred_at::date = :report_date
                              AND site_id = ANY(:site_ids)
                            """
                        ),
                        {"org_id": org_uuid, "report_date": report_date, "site_ids": site_ids},
                    )
                ).mappings().all()
                reported_site_ids = {row["site_id"] for row in reported_rows}

            sites = [
                {
                    "site_id": str(row["id"]),
                    "site_name": row["name"],
                    "project_id": str(row["project_id"]) if row["project_id"] else None,
                    "reported": row["id"] in reported_site_ids,
                }
                for row in site_rows
            ]

        return {
            "sites": sites,
            "reported_count": sum(1 for s in sites if s["reported"]),
            "not_reported_count": sum(1 for s in sites if not s["reported"]),
        }
