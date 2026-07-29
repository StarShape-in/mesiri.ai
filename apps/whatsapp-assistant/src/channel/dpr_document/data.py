"""Maps a DPR version's `payload` JSONB (backend/.../dpr.py's assembled
dict) into the shape template.py renders. Pure, no I/O -- mirrors
channel/receipt/data.py's split between data-shaping and layout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class DprActivityRow:
    work_type: str
    narrative: str
    status: str
    contractor: str
    quantities: str
    evidence_count: int


@dataclass(frozen=True, slots=True)
class DprIssueRow:
    issue_type: str
    severity: str
    narrative: str
    status: str


@dataclass(frozen=True, slots=True)
class DprTradeRow:
    trade: str
    headcount: int


@dataclass(frozen=True, slots=True)
class DprMaterialRow:
    material_name: str
    received: str
    used: str
    unit: str


@dataclass(frozen=True, slots=True)
class DprDocumentData:
    code: str
    project_name: str
    site_name: str
    report_date: str
    activities: list[DprActivityRow] = field(default_factory=list)
    issues: list[DprIssueRow] = field(default_factory=list)
    activity_count: int = 0
    open_issue_count: int = 0
    evidence_count: int = 0
    trades: list[DprTradeRow] = field(default_factory=list)
    headcount: int = 0
    labour_cost: str = "0"
    materials: list[DprMaterialRow] = field(default_factory=list)


def _pretty(label: object) -> str:
    if not label:
        return "—"
    return str(label).replace("_", " ").title()


def _quantities_text(quantities: list[dict[str, Any]]) -> str:
    if not quantities:
        return "—"
    return ", ".join(
        f"{q.get('quantity')} {q.get('unit')} {_pretty(q.get('work_type'))}".strip()
        for q in quantities
    )


def build_document_data(*, code: str, payload: dict[str, Any]) -> DprDocumentData:
    """Shape an assembled DPR payload (see backend/.../dpr.py's
    `assemble_site_report_payload`) into what the template renders. Missing
    fields degrade to placeholders rather than raising -- a partially-filled
    payload should still render a readable, honest document."""
    activities = [
        DprActivityRow(
            work_type=_pretty(a.get("work_type")),
            narrative=a.get("narrative") or "—",
            status=_pretty(a.get("status")),
            contractor=a.get("contractor") or "—",
            quantities=_quantities_text(a.get("quantities") or []),
            evidence_count=int(a.get("evidence_count") or 0),
        )
        for a in payload.get("activities", [])
    ]
    issues = [
        DprIssueRow(
            issue_type=_pretty(i.get("issue_type")),
            severity=_pretty(i.get("severity")),
            narrative=i.get("narrative") or "—",
            status=_pretty(i.get("status")),
        )
        for i in payload.get("issues", [])
    ]
    labour = payload.get("labour") or {}
    trades = [
        DprTradeRow(trade=_pretty(t.get("trade")), headcount=int(t.get("headcount") or 0))
        for t in labour.get("trades", [])
    ]
    materials = [
        DprMaterialRow(
            material_name=_pretty(m.get("material_name")),
            received=str(m.get("received") or "0"),
            used=str(m.get("used") or "0"),
            unit=m.get("unit") or "—",
        )
        for m in payload.get("materials", [])
    ]
    return DprDocumentData(
        code=code,
        project_name=payload.get("project_name") or "—",
        site_name=payload.get("site_name") or "—",
        report_date=payload.get("report_date") or "—",
        activities=activities,
        issues=issues,
        activity_count=int(payload.get("activity_count") or len(activities)),
        open_issue_count=int(payload.get("open_issue_count") or 0),
        evidence_count=int(payload.get("evidence_count") or 0),
        trades=trades,
        headcount=int(labour.get("headcount") or 0),
        labour_cost=str(labour.get("total_cost") or "0"),
        materials=materials,
    )
