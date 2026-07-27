"""build_site_report_payload -- #16 Daily Report Generation's pure shaping.

Protects the payload shape the assistant-side PDF renderer and the future
manager-review UI both depend on: activities carry their quantities and
evidence counts, issues carry severity/status, and the summary counts
(activity_count/open_issue_count/evidence_count) are derived correctly
rather than trusted from the caller.
"""

from __future__ import annotations

import datetime
import uuid

from mesiri.application.dpr.assembly import build_site_report_payload

ACTIVITY_1 = uuid.uuid4()
ACTIVITY_2 = uuid.uuid4()


def test_empty_day_produces_a_zeroed_payload():
    payload = build_site_report_payload(
        project_name="Skyline Towers",
        site_name="Block A",
        report_date=datetime.date(2026, 7, 27),
        activity_rows=[],
        quantities_by_activity={},
        evidence_count_by_activity={},
        issue_rows=[],
    )
    assert payload["activity_count"] == 0
    assert payload["open_issue_count"] == 0
    assert payload["evidence_count"] == 0
    assert payload["activities"] == []
    assert payload["issues"] == []


def test_activity_carries_its_own_quantities_and_evidence_count():
    payload = build_site_report_payload(
        project_name="Skyline Towers",
        site_name="Block A",
        report_date=datetime.date(2026, 7, 27),
        activity_rows=[
            {
                "id": ACTIVITY_1,
                "work_type": "plastering",
                "narrative": "180 sqm done",
                "status": "IN_PROGRESS",
                "contractor": "ABC Contractors",
            }
        ],
        quantities_by_activity={
            ACTIVITY_1: [{"work_type": "plastering", "quantity": "180", "unit": "sqm"}]
        },
        evidence_count_by_activity={ACTIVITY_1: 3},
        issue_rows=[],
    )
    assert payload["activity_count"] == 1
    activity = payload["activities"][0]
    assert activity["quantities"] == [{"work_type": "plastering", "quantity": "180", "unit": "sqm"}]
    assert activity["evidence_count"] == 3
    assert payload["evidence_count"] == 3


def test_activity_with_no_quantities_or_evidence_defaults_to_empty_not_missing():
    payload = build_site_report_payload(
        project_name="Skyline Towers",
        site_name="Block A",
        report_date=datetime.date(2026, 7, 27),
        activity_rows=[{"id": ACTIVITY_2, "work_type": "excavation", "narrative": None,
                         "status": "PLANNED", "contractor": None}],
        quantities_by_activity={},
        evidence_count_by_activity={},
        issue_rows=[],
    )
    activity = payload["activities"][0]
    assert activity["quantities"] == []
    assert activity["evidence_count"] == 0


def test_open_issue_count_only_counts_open_not_resolved():
    payload = build_site_report_payload(
        project_name="Skyline Towers",
        site_name="Block A",
        report_date=datetime.date(2026, 7, 27),
        activity_rows=[],
        quantities_by_activity={},
        evidence_count_by_activity={},
        issue_rows=[
            {"issue_type": "MATERIAL_SHORTAGE", "severity": "HIGH", "narrative": "cement short",
             "status": "OPEN", "delay_duration_minutes": 60},
            {"issue_type": "WEATHER", "severity": "LOW", "narrative": "rain earlier",
             "status": "RESOLVED", "delay_duration_minutes": 30},
        ],
    )
    assert len(payload["issues"]) == 2
    assert payload["open_issue_count"] == 1


def test_evidence_count_sums_across_all_activities():
    payload = build_site_report_payload(
        project_name="Skyline Towers",
        site_name="Block A",
        report_date=datetime.date(2026, 7, 27),
        activity_rows=[
            {"id": ACTIVITY_1, "work_type": "plastering", "narrative": None,
             "status": "COMPLETED", "contractor": None},
            {"id": ACTIVITY_2, "work_type": "excavation", "narrative": None,
             "status": "COMPLETED", "contractor": None},
        ],
        quantities_by_activity={},
        evidence_count_by_activity={ACTIVITY_1: 2, ACTIVITY_2: 5},
        issue_rows=[],
    )
    assert payload["evidence_count"] == 7


def test_report_date_is_serialized_as_iso_string():
    payload = build_site_report_payload(
        project_name="X", site_name="Y", report_date=datetime.date(2026, 7, 27),
        activity_rows=[], quantities_by_activity={}, evidence_count_by_activity={}, issue_rows=[],
    )
    assert payload["report_date"] == "2026-07-27"
