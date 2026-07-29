"""ConfirmedActionV2 -> CorrectActivityQuantityCommand mapping — unit tests (pure, no I/O)."""

from __future__ import annotations

from decimal import Decimal

from mesiri.application.progress.mapper import build_correct_activity_quantity_command
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PROGRESS_UPDATE_ID = "55555555-5555-4555-8555-555555555555"
UNIT_ID = "66666666-6666-4666-8666-666666666666"


def _confirmed(fields: dict) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.CORRECT_ACTIVITY_QUANTITY,
        organization_id=ORG,
        user_id=USR,
        fields=fields,
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )


def test_maps_correction_fields():
    cmd = build_correct_activity_quantity_command(
        _confirmed(
            {
                "progress_update_id": PROGRESS_UPDATE_ID,
                "new_quantity": 180,
                "unit": "sqm",
                "unit_id": UNIT_ID,
                "reason": "misheard the number",
            }
        )
    )
    assert cmd.idempotency_key == "wf_1"
    assert cmd.progress_update_id == PROGRESS_UPDATE_ID
    assert cmd.new_quantity == Decimal("180")
    assert cmd.new_unit == "sqm"
    assert cmd.new_unit_id == UNIT_ID
    assert cmd.reason == "misheard the number"
    assert cmd.created_by == USR


def test_missing_reason_maps_to_none():
    cmd = build_correct_activity_quantity_command(
        _confirmed({"progress_update_id": PROGRESS_UPDATE_ID, "new_quantity": 180, "unit": "sqm"})
    )
    assert cmd.reason is None


def test_source_defaults_to_whatsapp_text():
    cmd = build_correct_activity_quantity_command(
        _confirmed({"progress_update_id": PROGRESS_UPDATE_ID, "new_quantity": 180, "unit": "sqm"})
    )
    assert cmd.source == "whatsapp_text"
