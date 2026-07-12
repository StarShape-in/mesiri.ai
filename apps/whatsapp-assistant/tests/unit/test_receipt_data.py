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
