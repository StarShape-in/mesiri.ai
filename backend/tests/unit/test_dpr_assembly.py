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


def _base_payload(**overrides):
    base = dict(
        project_name="Skyline Towers",
        site_name="Block A",
        report_date=datetime.date(2026, 7, 27),
        activity_rows=[],
        quantities_by_activity={},
        evidence_count_by_activity={},
        issue_rows=[],
    )
    base.update(overrides)
    return build_site_report_payload(**base)


def test_missing_labour_and_material_args_default_to_zeroed_sections():
    """Every existing caller (this test file's own calls above) never passed
    labour_lines/material_movement_rows -- must still shape a valid,
    honestly-empty section rather than raising or omitting the key."""
    payload = _base_payload()
    assert payload["labour"] == {"headcount": 0, "named_count": 0, "trades": [], "total_cost": "0"}
    assert payload["materials"] == []


def test_labour_headcount_sums_named_and_group_lines():
    payload = _base_payload(
        labour_lines=[
            {"worker_name": "Ravi", "trade": "mason", "headcount": 1, "daily_wage": "800"},
            {"worker_name": None, "trade": "helper", "headcount": 12, "daily_wage": "600"},
        ]
    )
    labour = payload["labour"]
    assert labour["headcount"] == 13
    assert labour["named_count"] == 1
    assert {"trade": "mason", "headcount": 1} in labour["trades"]
    assert {"trade": "helper", "headcount": 12} in labour["trades"]


def test_labour_cost_multiplies_daily_wage_by_headcount():
    payload = _base_payload(
        labour_lines=[
            {"worker_name": "Ravi", "trade": "mason", "headcount": 1, "daily_wage": "800"},
            {"worker_name": None, "trade": "helper", "headcount": 12, "daily_wage": "600"},
        ]
    )
    assert payload["labour"]["total_cost"] == "8000"


def test_labour_line_with_no_wage_contributes_zero_cost_not_an_error():
    payload = _base_payload(
        labour_lines=[{"worker_name": "Ravi", "trade": "mason", "headcount": 1, "daily_wage": None}]
    )
    assert payload["labour"]["total_cost"] == "0"


def test_labour_line_with_no_trade_is_excluded_from_trades_breakdown_but_still_counted():
    payload = _base_payload(
        labour_lines=[{"worker_name": "Ravi", "trade": None, "headcount": 1, "daily_wage": "800"}]
    )
    labour = payload["labour"]
    assert labour["headcount"] == 1
    assert labour["trades"] == []


def test_material_received_and_used_are_summed_separately_per_material():
    payload = _base_payload(
        material_movement_rows=[
            {"material_id": "m1", "material_name": "Cement", "unit": "bags",
             "movement_type": "RECEIPT", "quantity": "50"},
            {"material_id": "m1", "material_name": "Cement", "unit": "bags",
             "movement_type": "ISSUE", "quantity": "20"},
        ]
    )
    materials = payload["materials"]
    assert len(materials) == 1
    assert materials[0]["material_name"] == "Cement"
    assert materials[0]["received"] == "50"
    assert materials[0]["used"] == "20"


def test_material_movements_for_different_materials_stay_separate():
    payload = _base_payload(
        material_movement_rows=[
            {"material_id": "m1", "material_name": "Cement", "unit": "bags",
             "movement_type": "RECEIPT", "quantity": "50"},
            {"material_id": "m2", "material_name": "Steel", "unit": "kg",
             "movement_type": "ISSUE", "quantity": "120"},
        ]
    )
    materials = {m["material_name"]: m for m in payload["materials"]}
    assert materials["Cement"]["received"] == "50"
    assert materials["Cement"]["used"] == "0"
    assert materials["Steel"]["used"] == "120"
    assert materials["Steel"]["received"] == "0"
