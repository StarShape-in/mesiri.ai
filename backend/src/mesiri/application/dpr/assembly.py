"""Pure payload shaping for a SITE-level DPR (#16 Daily Report Generation).

Takes raw DB rows (already fetched by infrastructure/postgres/repositories/
dpr.py) and shapes them into the plain JSON-safe dict stored as
`daily_report_versions.payload` and consumed by the assistant-side PDF
renderer (channel/dpr_document/). No I/O here -- the split exists so this
shaping is unit-testable without a live database, same reasoning as
runtime/labour_query_service.py's `_summarize`.
"""

from __future__ import annotations

import datetime
from typing import Any


def build_site_report_payload(
    *,
    project_name: str | None,
    site_name: str | None,
    report_date: datetime.date,
    activity_rows: list[dict[str, Any]],
    quantities_by_activity: dict[Any, list[dict[str, Any]]],
    evidence_count_by_activity: dict[Any, int],
    issue_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compose the payload dict. `activity_rows`/`issue_rows` are already
    scoped to the one site+date by the caller's query -- this function does
    no filtering, only shaping."""
    activities = [
        {
            "work_type": row.get("work_type"),
            "narrative": row.get("narrative"),
            "status": row.get("status"),
            "contractor": row.get("contractor"),
            "quantities": quantities_by_activity.get(row["id"], []),
            "evidence_count": evidence_count_by_activity.get(row["id"], 0),
        }
        for row in activity_rows
    ]
    issues = [
        {
            "issue_type": row.get("issue_type"),
            "severity": row.get("severity"),
            "narrative": row.get("narrative"),
            "status": row.get("status"),
            "delay_duration_minutes": row.get("delay_duration_minutes"),
        }
        for row in issue_rows
    ]
    return {
        "project_name": project_name,
        "site_name": site_name,
        "report_date": report_date.isoformat(),
        "activities": activities,
        "activity_count": len(activities),
        "issues": issues,
        "open_issue_count": sum(1 for i in issues if i["status"] == "OPEN"),
        "evidence_count": sum(a["evidence_count"] for a in activities),
    }
