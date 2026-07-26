"""Unit tests for channel.receipt.data -- pure, no playwright/browser needed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from channel.receipt.data import build_receipt_data
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"


@dataclass(frozen=True, slots=True)
class _Named:
    id: str
    name: str


def _draft(action_type: DraftActionType, fields: dict) -> DraftActionV2:
    return DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=action_type,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=SITE,
        fields=fields,
    )


def test_receipt_reflects_material_usage():
    draft = _draft(
        DraftActionType.RECORD_MATERIAL_USAGE,
        {"material_name": "cement", "quantity": 18, "unit": "bags", "work_item": "Slab casting"},
    )
    data = build_receipt_data(
        draft,
        material_row_id="abcd1234-0000",
        reporter_name="Mohammed",
        projects=[_Named(PRJ, "Riverside Tower")],
        sites=[_Named(SITE, "Site B")],
        confirmed_at=datetime(2026, 7, 12, 10, 57, tzinfo=UTC),
    )
    assert data.category == "Material usage"
    assert data.value == "18 bags"
    assert data.location[0].text == "Riverside Tower"
    assert data.location[1].text == "Site B"
    assert data.record_id.startswith("MU-120726-")
    # work_item shows up as "Used for" in a section, not silently dropped
    assert any(f.label == "Used for" and f.value == "Slab casting" for s in data.sections for f in s)


def test_receipt_reflects_material_receipt():
    draft = _draft(
        DraftActionType.RECORD_MATERIAL_RECEIPT,
        {"material_name": "cement", "quantity": 50, "unit": "bags", "supplier": "UltraTech"},
    )
    data = build_receipt_data(
        draft,
        material_row_id="ef567890-0000",
        reporter_name="Priya",
        projects=[_Named(PRJ, "Riverside Tower")],
        sites=[_Named(SITE, "Site B")],
        confirmed_at=datetime(2026, 7, 12, 9, 0, tzinfo=UTC),
    )
    assert data.category == "Material receipt"
    assert data.record_id.startswith("MR-120726-")
    assert any(f.label == "Supplier" and f.value == "UltraTech" for s in data.sections for f in s)


def test_receipt_degrades_gracefully_with_missing_optional_data():
    """Missing reporter/project/site/supplier must never raise -- show a
    plain dash instead, since a receipt with a KeyError is worse than one
    with a placeholder."""
    draft = _draft(
        DraftActionType.RECORD_MATERIAL_RECEIPT,
        {"material_name": "sand", "quantity": 5, "unit": "tons"},
    )
    data = build_receipt_data(
        draft,
        material_row_id="ghij0000-0000",
        reporter_name=None,
        projects=[],
        sites=[],
        confirmed_at=datetime(2026, 7, 12, 9, 0, tzinfo=UTC),
    )
    assert data.location[0].text == "—"
    assert data.location[1].text == "—"
    assert any(f.label == "Reported by" and f.value == "—" for s in data.sections for f in s)


def test_two_record_types_share_identical_shape():
    """The whole point: one template, never a different layout per type --
    both action types must produce the same section/field structure."""
    receipt = _draft(
        DraftActionType.RECORD_MATERIAL_RECEIPT,
        {"material_name": "cement", "quantity": 50, "unit": "bags"},
    )
    usage = _draft(
        DraftActionType.RECORD_MATERIAL_USAGE,
        {"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    common = {
        "material_row_id": "xxxx-0000",
        "reporter_name": "Mohammed",
        "projects": [_Named(PRJ, "Riverside Tower")],
        "sites": [_Named(SITE, "Site B")],
        "confirmed_at": datetime(2026, 7, 12, 9, 0, tzinfo=UTC),
    }
    receipt_data = build_receipt_data(receipt, **common)
    usage_data = build_receipt_data(usage, **common)
    assert len(receipt_data.sections) == len(usage_data.sections)
    assert [len(s) for s in receipt_data.sections] == [len(s) for s in usage_data.sections]


def _labour_receipt(lines: list[dict]):
    return build_receipt_data(
        _draft(DraftActionType.RECORD_LABOUR_ATTENDANCE, {"lines": lines}),
        material_row_id="stub-9999abcd",
        reporter_name="Mohammed",
        projects=[_Named(PRJ, "Riverside Tower")],
        sites=[_Named(SITE, "Site B")],
        confirmed_at=datetime(2026, 7, 26, 10, 57, tzinfo=UTC),
    )


def test_labour_receipt_is_not_labelled_material():
    """The bug this fixes: attendance fell through to the `else` branch and
    every confirmed attendance came back to the user as a *Material usage*
    receipt with an MU- record id. The user is told what they recorded, so
    getting this wrong is not cosmetic."""
    data = _labour_receipt([{"worker_name": "Ravi", "trade": "mason", "headcount": 1}])
    assert data.category == "Labour attendance"
    assert "Material" not in data.category
    assert "Material" not in data.subtitle
    assert data.record_id.startswith("LA-")


def test_labour_receipt_totals_people_across_named_and_group_lines():
    data = _labour_receipt(
        [
            {"worker_name": "Ravi", "trade": "mason", "headcount": 1},
            {"worker_name": "Arun", "trade": "painter", "headcount": 1},
            {"worker_name": None, "trade": "helper", "headcount": 12},
        ]
    )
    assert data.value == "14"
    assert data.subtitle == "14 workers recorded"


def test_labour_receipt_shows_how_the_headcount_breaks_down():
    """P10's distinction -- who was named versus who was only counted --
    belongs on the record the user keeps."""
    data = _labour_receipt(
        [
            {"worker_name": "Ravi", "trade": "mason", "headcount": 1},
            {"worker_name": None, "trade": "helper", "headcount": 12},
        ]
    )
    workers_field = data.sections[0][0]
    assert workers_field.label == "Workers"
    assert workers_field.value == "13 (1 named, 12 by headcount)"


def test_labour_receipt_wording_for_all_named_and_all_counted():
    all_named = _labour_receipt([{"worker_name": "Ravi", "trade": "mason", "headcount": 1}])
    assert all_named.sections[0][0].value == "1 named"
    all_counted = _labour_receipt([{"worker_name": None, "trade": "helper", "headcount": 9}])
    assert all_counted.sections[0][0].value == "9 (by headcount)"


def test_labour_receipt_lists_trades_without_duplicates():
    data = _labour_receipt(
        [
            {"worker_name": "Ravi", "trade": "mason", "headcount": 1},
            {"worker_name": "Suresh", "trade": "mason", "headcount": 1},
            {"worker_name": None, "trade": "bar_bender", "headcount": 4},
        ]
    )
    assert data.sections[0][1].value == "Mason, Bar Bender"


def test_labour_receipt_survives_an_empty_attendance():
    data = _labour_receipt([])
    assert data.category == "Labour attendance"
    assert data.sections[0][0].value == "—"


def test_labour_receipt_singular_worker_reads_naturally():
    data = _labour_receipt([{"worker_name": "Ravi", "trade": "mason", "headcount": 1}])
    assert data.subtitle == "1 worker recorded"
