"""DPR PDF document shaping/rendering -- #16 Daily Report Generation.

Covers data.py's payload -> DprDocumentData mapping (pure) and template.py's
Jinja2 render (pure, no Playwright/no live browser needed -- render.py's
Playwright driving is untestable without a headless browser and is not
covered here, same convention as channel/receipt/render.py).
"""

from __future__ import annotations

import pytest

from channel.dpr_document.data import build_document_data

# render_html needs jinja2, which -- like playwright -- lives behind the
# "receipt" extra and is intentionally absent from the core CI install
# (see pyproject.toml's comment on that group and channel/receipt/template.py,
# which is untested for the same reason). build_document_data is pure and
# needs no such guard.
jinja2 = pytest.importorskip("jinja2")
from channel.dpr_document.template import render_html  # noqa: E402


def _payload(**overrides):
    base = {
        "project_name": "Skyline Towers",
        "site_name": "Block A",
        "report_date": "2026-07-27",
        "activities": [],
        "activity_count": 0,
        "issues": [],
        "open_issue_count": 0,
        "evidence_count": 0,
    }
    base.update(overrides)
    return base


def test_build_document_data_maps_project_and_site_names():
    data = build_document_data(code="DPR-20260727-AB12", payload=_payload())
    assert data.code == "DPR-20260727-AB12"
    assert data.project_name == "Skyline Towers"
    assert data.site_name == "Block A"
    assert data.report_date == "2026-07-27"


def test_build_document_data_formats_quantities_as_readable_text():
    payload = _payload(
        activities=[
            {
                "work_type": "plastering",
                "narrative": "180 sqm done",
                "status": "IN_PROGRESS",
                "contractor": "ABC Contractors",
                "quantities": [{"work_type": "plastering", "quantity": "180", "unit": "sqm"}],
                "evidence_count": 2,
            }
        ],
        activity_count=1,
    )
    data = build_document_data(code="DPR-1", payload=payload)
    activity = data.activities[0]
    assert activity.work_type == "Plastering"
    assert "180" in activity.quantities
    assert "sqm" in activity.quantities
    assert activity.evidence_count == 2


def test_build_document_data_missing_fields_degrade_to_placeholders():
    payload = _payload(
        activities=[
            {"work_type": None, "narrative": None, "status": None, "contractor": None,
             "quantities": [], "evidence_count": 0}
        ],
        activity_count=1,
    )
    data = build_document_data(code="DPR-1", payload=payload)
    activity = data.activities[0]
    assert activity.narrative == "—"
    assert activity.contractor == "—"
    assert activity.quantities == "—"


def test_render_html_includes_project_site_and_code():
    data = build_document_data(code="DPR-20260727-AB12", payload=_payload())
    html = render_html(data)
    assert "Skyline Towers" in html
    assert "Block A" in html
    assert "DPR-20260727-AB12" in html


def test_render_html_shows_empty_state_for_no_activities_or_issues():
    data = build_document_data(code="DPR-1", payload=_payload())
    html = render_html(data)
    assert "No activities logged" in html
    assert "No issues reported" in html


def test_render_html_lists_each_activity_and_issue():
    payload = _payload(
        activities=[
            {"work_type": "excavation", "narrative": "trench dug", "status": "COMPLETED",
             "contractor": "XYZ Co", "quantities": [], "evidence_count": 1}
        ],
        activity_count=1,
        issues=[
            {"issue_type": "WEATHER", "severity": "HIGH", "narrative": "heavy rain",
             "status": "OPEN"}
        ],
        open_issue_count=1,
    )
    data = build_document_data(code="DPR-1", payload=payload)
    html = render_html(data)
    assert "trench dug" in html
    assert "XYZ Co" in html
    assert "heavy rain" in html
    assert "severity-high" in html
