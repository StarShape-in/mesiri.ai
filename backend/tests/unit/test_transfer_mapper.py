"""ConfirmedActionV2 -> TransferMoneyCommand mapping — unit tests (pure, no I/O)."""

from __future__ import annotations

from decimal import Decimal

from mesiri.application.finance.transfer_mapper import build_command
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
ACC_A = "55555555-5555-4555-8555-555555555555"
ACC_B = "66666666-6666-4666-8666-666666666666"


def _confirmed(fields: dict) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.TRANSFER_MONEY,
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


def test_maps_transfer_fields():
    cmd = build_command(
        _confirmed(
            {
                "amount": 500,
                "from_account_id": ACC_A,
                "to_account_id": ACC_B,
                "created_by_role": "ADMIN",
            }
        )
    )
    assert cmd.idempotency_key == "wf_1"
    assert cmd.from_account_id == ACC_A
    assert cmd.to_account_id == ACC_B
    assert cmd.amount == Decimal("500")
    assert cmd.created_by_role == "ADMIN"
    assert cmd.created_by == USR


def test_missing_role_maps_to_none():
    cmd = build_command(_confirmed({"amount": 500, "from_account_id": ACC_A, "to_account_id": ACC_B}))
    assert cmd.created_by_role is None


def test_non_numeric_amount_defaults_to_zero_for_validation_to_catch():
    cmd = build_command(
        _confirmed({"amount": "not a number", "from_account_id": ACC_A, "to_account_id": ACC_B})
    )
    assert cmd.amount == Decimal("0")


def test_missing_account_ids_map_to_empty_strings_for_validation_to_catch():
    cmd = build_command(_confirmed({"amount": 500}))
    assert cmd.from_account_id == ""
    assert cmd.to_account_id == ""
