"""domains/dpr/pdf.py -- pure fpdf2 rendering, no I/O.

Fixes the gap where a rendered DPR PDF already existed in R2
(daily_report_versions.rendered_object_key) but nothing in the backend or
dashboard could ever reach it, and there was no fallback for a report whose
version hasn't been picked up by the nightly Playwright cron yet
(runtime/render_pending_dpr_pdfs.py). This module is that fallback: a plain
tabular PDF built directly from the same payload shape
(application/dpr/assembly.py::build_site_report_payload), using fpdf2
instead of adding Playwright to the backend process (ADR-D8).
"""

from __future__ import annotations

from mesiri.domains.dpr.pdf import render_dpr_pdf_bytes

_FULL_PAYLOAD = {
    "project_name": "Skyline Towers",
    "site_name": "Site A",
    "report_date": "2026-07-20",
    "activities": [
        {
            "work_type": "Plastering",
            "narrative": "Second floor east wing plastering completed.",
            "status": "COMPLETED",
            "contractor": "ABC Contractors",
            "quantities": [{"quantity": "120", "unit": "sqm"}],
            "evidence_count": 3,
        }
    ],
    "activity_count": 1,
    "issues": [
        {
            "issue_type": "MATERIAL_SHORTAGE",
            "severity": "HIGH",
            "narrative": "Cement delivery delayed by 2 days.",
            "status": "OPEN",
            "delay_duration_minutes": 240,
        }
    ],
    "open_issue_count": 1,
    "evidence_count": 3,
}

_EMPTY_PAYLOAD = {
    "project_name": None,
    "site_name": None,
    "report_date": "2026-07-20",
    "activities": [],
    "activity_count": 0,
    "issues": [],
    "open_issue_count": 0,
    "evidence_count": 0,
}


def test_renders_valid_pdf_bytes_for_a_populated_payload():
    pdf_bytes = render_dpr_pdf_bytes(
        code="DPR-001",
        report_date="2026-07-20",
        project_name="Skyline Towers",
        site_name="Site A",
        workflow_status="approved",
        payload=_FULL_PAYLOAD,
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_renders_without_error_for_an_empty_payload():
    """A report with no activities/issues yet (freshly created) must still
    produce a valid PDF -- not raise on empty lists or None project/site."""
    pdf_bytes = render_dpr_pdf_bytes(
        code=None,
        report_date="2026-07-20",
        project_name=None,
        site_name=None,
        workflow_status="draft",
        payload=_EMPTY_PAYLOAD,
    )
    assert pdf_bytes.startswith(b"%PDF")


def test_renders_labour_and_material_sections_when_present():
    payload = dict(
        _EMPTY_PAYLOAD,
        labour={
            "headcount": 13,
            "named_count": 1,
            "trades": [{"trade": "Mason", "headcount": 1}, {"trade": "Helper", "headcount": 12}],
            "total_cost": "8000",
        },
        materials=[{"material_name": "Cement", "unit": "bags", "received": "50", "used": "20"}],
    )
    pdf_bytes = render_dpr_pdf_bytes(
        code="DPR-003",
        report_date="2026-07-20",
        project_name="Skyline Towers",
        site_name="Site A",
        workflow_status="draft",
        payload=payload,
    )
    assert pdf_bytes.startswith(b"%PDF")


def test_renders_without_error_when_labour_and_materials_keys_are_absent():
    """Pre-existing payloads (created before this feature) never had these
    keys at all -- must still render, not KeyError."""
    pdf_bytes = render_dpr_pdf_bytes(
        code="DPR-004",
        report_date="2026-07-20",
        project_name="Skyline Towers",
        site_name="Site A",
        workflow_status="draft",
        payload=_EMPTY_PAYLOAD,
    )
    assert pdf_bytes.startswith(b"%PDF")


def test_handles_missing_optional_fields_in_activity_and_issue_rows():
    """quantities/contractor/narrative etc. are all optional per
    build_site_report_payload -- a row with only the required keys must not
    crash the renderer."""
    payload = {
        "project_name": "P",
        "site_name": "S",
        "report_date": "2026-07-20",
        "activities": [{"work_type": None, "quantities": []}],
        "activity_count": 1,
        "issues": [{"issue_type": None}],
        "open_issue_count": 0,
        "evidence_count": 0,
    }
    pdf_bytes = render_dpr_pdf_bytes(
        code="DPR-002",
        report_date="2026-07-20",
        project_name="P",
        site_name="S",
        workflow_status="in_review",
        payload=payload,
    )
    assert pdf_bytes.startswith(b"%PDF")
