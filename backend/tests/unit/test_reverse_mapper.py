"""ConfirmedActionV2 -> ReverseTransactionCommand mapping — unit tests (pure, no I/O)."""

from __future__ import annotations

from mesiri.application.finance.reverse_mapper import build_command
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
EXPENSE_ID = "55555555-5555-4555-8555-555555555555"
TRANSACTION_ID = "66666666-6666-4666-8666-666666666666"


def _confirmed(fields: dict) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.REVERSE_TRANSACTION,
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


def test_maps_expense_reversal_fields():
    cmd = build_command(
        _confirmed({"target_kind": "expense", "expense_id": EXPENSE_ID, "created_by_role": "ADMIN"})
    )
    assert cmd.idempotency_key == "wf_1"
    assert cmd.target_kind == "expense"
    assert cmd.expense_id == EXPENSE_ID
    assert cmd.money_transaction_id is None
    assert cmd.created_by_role == "ADMIN"
    assert cmd.created_by == USR


def test_maps_transfer_reversal_fields():
    cmd = build_command(
        _confirmed(
            {
                "target_kind": "transfer",
                "money_transaction_id": TRANSACTION_ID,
                "created_by_role": "FINANCE",
            }
        )
    )
    assert cmd.target_kind == "transfer"
    assert cmd.money_transaction_id == TRANSACTION_ID
    assert cmd.expense_id is None


def test_missing_role_maps_to_none():
    cmd = build_command(_confirmed({"target_kind": "expense", "expense_id": EXPENSE_ID}))
    assert cmd.created_by_role is None


def test_missing_target_kind_maps_to_empty_string_for_validation_to_catch():
    cmd = build_command(_confirmed({}))
    assert cmd.target_kind == ""
