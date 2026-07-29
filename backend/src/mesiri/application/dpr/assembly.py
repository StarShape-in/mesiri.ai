"""Pure payload shaping for a SITE-level DPR (#16 Daily Report Generation).

Takes raw DB rows (already fetched by infrastructure/postgres/repositories/
dpr.py) and shapes them into the plain JSON-safe dict stored as
`daily_report_versions.payload` and consumed by the assistant-side PDF
renderer (channel/dpr_document/). No I/O here -- the split exists so this
shaping is unit-testable without a live database, same reasoning as
runtime/labour_query_service.py's `_summarize`.

`labour_lines`/`material_movement_rows` are optional (default to empty) so
existing callers/tests built before this data existed keep working -- a
report with nothing recorded in either module still shapes a valid, honest
zeroed section rather than omitting the key.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any


def _labour_summary(labour_lines: list[dict[str, Any]]) -> dict[str, Any]:
    """Headcount, per-trade breakdown, and cost for one site+date -- mirrors
    runtime/labour_query_service.py's `summarize_attendance` shape (the
    WhatsApp "how many workers today?" query), so the same figures a
    supervisor already sees in chat are what a client sees in the report.
    `daily_wage` is copied onto each attendance line at recording time (see
    migration 0371), never re-read from workforce_workers, so this cost is
    what that day actually cost, not what workers are paid today."""
    headcount = 0
    named_count = 0
    trade_counts: dict[str, int] = {}
    total_cost = Decimal("0")
    for line in labour_lines:
        try:
            count = int(line.get("headcount") or 1)
        except (TypeError, ValueError):
            count = 1
        headcount += count
        if str(line.get("worker_name") or "").strip():
            named_count += 1
        trade = str(line.get("trade") or "").strip()
        if trade:
            trade_counts[trade] = trade_counts.get(trade, 0) + count
        wage = line.get("daily_wage")
        if wage is not None:
            total_cost += Decimal(str(wage)) * count
    return {
        "headcount": headcount,
        "named_count": named_count,
        "trades": [{"trade": t, "headcount": c} for t, c in trade_counts.items()],
        "total_cost": str(total_cost),
    }


def _material_summary(movement_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Received/used quantities per material for one site+date, derived from
    material_movements the same way runtime/inventory_query.py re-aggregates
    stock levels -- RECEIPT adds to `received`, ISSUE adds to `used`. Day-
    scoped (unlike inventory_query's running stock total), since a DPR
    reports what happened on report_date, not the site's current inventory
    position. Cost is deliberately not included here: material_receipts.
    unit_cost is nullable and inconsistently recorded, unlike labour's wage
    (always copied at recording time) -- a partial cost figure would read as
    complete and mislead more than omitting it."""
    materials: dict[Any, dict[str, Any]] = {}
    for row in movement_rows:
        key = row.get("material_id")
        entry = materials.setdefault(
            key,
            {"material_name": row.get("material_name"), "unit": row.get("unit"),
             "received": Decimal("0"), "used": Decimal("0")},
        )
        quantity = Decimal(str(row.get("quantity") or 0))
        if row.get("movement_type") == "RECEIPT":
            entry["received"] += quantity
        elif row.get("movement_type") == "ISSUE":
            entry["used"] += quantity
    return [
        {
            "material_name": entry["material_name"],
            "unit": entry["unit"],
            "received": str(entry["received"]),
            "used": str(entry["used"]),
        }
        for entry in materials.values()
    ]


def build_site_report_payload(
    *,
    project_name: str | None,
    site_name: str | None,
    report_date: datetime.date,
    activity_rows: list[dict[str, Any]],
    quantities_by_activity: dict[Any, list[dict[str, Any]]],
    evidence_count_by_activity: dict[Any, int],
    issue_rows: list[dict[str, Any]],
    labour_lines: list[dict[str, Any]] | None = None,
    material_movement_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compose the payload dict. `activity_rows`/`issue_rows`/`labour_lines`/
    `material_movement_rows` are already scoped to the one site+date by the
    caller's query -- this function does no filtering, only shaping."""
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
        "labour": _labour_summary(labour_lines or []),
        "materials": _material_summary(material_movement_rows or []),
    }
