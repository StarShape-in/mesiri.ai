"""ConfirmedAction v2 contract validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import CONTRACT_VERSION, ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
WF = "11111111-1111-4111-8111-1111111111aa"


def _draft() -> DraftActionV2:
    return DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id=WF,
        action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
        organization_id=ORG,
        user_id=USR,
        fields={"material_name": "cement", "quantity": 20, "unit": "bags"},
    )


def test_version_constant():
    assert CONTRACT_VERSION == "v2"


def test_round_trip_with_nested_draft_action():
    confirmed = ConfirmedActionV2(
        confirmed_action_id="confirmed_1",
        workflow_instance_id=WF,
        correlation_id="cor_1",
        draft_action=_draft(),
        confirmed_by_user_id=USR,
    )
    dumped = confirmed.model_dump(mode="json")
    assert dumped["version"] == "v2"
    assert dumped["draft_action"]["action_type"] == "record_material_receipt"
    restored = ConfirmedActionV2.model_validate(dumped)
    assert restored == confirmed


def test_confirmed_by_user_id_must_be_canonical_uuid():
    with pytest.raises(ValidationError):
        ConfirmedActionV2(
            confirmed_action_id="confirmed_1",
            workflow_instance_id=WF,
            correlation_id="cor_1",
            draft_action=_draft(),
            confirmed_by_user_id="not-a-uuid",
        )


def test_extra_field_forbidden():
    with pytest.raises(ValidationError):
        ConfirmedActionV2.model_validate(
            {
                "confirmed_action_id": "confirmed_1",
                "workflow_instance_id": WF,
                "correlation_id": "cor_1",
                "draft_action": _draft().model_dump(mode="json"),
                "confirmed_by_user_id": USR,
                "confirmed_at": "2026-07-08T10:00:00Z",
            }
        )
