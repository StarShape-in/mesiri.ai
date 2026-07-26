"""Reverse workflow nodes — unit tests (pure functions, no LangGraph needed)."""

from __future__ import annotations

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from workflows.reverse.nodes import build_draft, request_confirmation

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
EXPENSE_ID = "55555555-5555-4555-8555-555555555555"
TRANSACTION_ID = "66666666-6666-4666-8666-666666666666"


def _base_state(fields: dict) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": WorkflowKey.REVERSE.value,
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": None,
        "site_id": None,
        "collected_fields": fields,
    }


def test_expense_target_builds_a_draft():
    state = _base_state(
        {
            "target_kind": "expense",
            "expense_id": EXPENSE_ID,
            "created_by_role": "ADMIN",
            "reversal_amount": "700.00",
            "reversal_description": "diesel refill",
            "reversal_occurred_date": "2026-07-25",
        }
    )
    update = build_draft(state)
    draft = update["draft_action"]
    assert draft.action_type is DraftActionType.REVERSE_TRANSACTION
    assert draft.fields["expense_id"] == EXPENSE_ID
    assert draft.fields["target_kind"] == "expense"
    assert draft.fields["created_by_role"] == "ADMIN"
    # Display-only, but kept (unlike other finance workflows' plumbing) --
    # these come from a real DB read (runtime/reversal_query.py), never an
    # unresolved AI hint, so channel/receipt/data.py's build_receipt_data
    # can show a real reversal receipt with them.
    assert draft.fields["reversal_amount"] == "700.00"
    assert draft.fields["reversal_description"] == "diesel refill"


def test_transfer_target_builds_a_draft():
    state = _base_state(
        {
            "target_kind": "transfer",
            "money_transaction_id": TRANSACTION_ID,
            "created_by_role": "FINANCE",
            "reversal_amount": "5000.00",
            "reversal_from_account_name": "Company Bank",
            "reversal_to_account_name": "Site Cash",
        }
    )
    update = build_draft(state)
    draft = update["draft_action"]
    assert draft.fields["money_transaction_id"] == TRANSACTION_ID
    assert draft.fields["target_kind"] == "transfer"
    assert draft.fields["reversal_from_account_name"] == "Company Bank"
    assert draft.fields["reversal_to_account_name"] == "Site Cash"


def test_no_expense_found_completes_without_a_draft():
    state = _base_state({"target_kind": "expense", "created_by_role": "ADMIN"})
    update = build_draft(state)
    assert "draft_action" not in update
    assert "no confirmed expenses" in update["pending_prompt"]


def test_no_transfer_found_completes_without_a_draft():
    state = _base_state({"target_kind": "transfer", "created_by_role": "ADMIN"})
    update = build_draft(state)
    assert "draft_action" not in update
    assert "no transfers" in update["pending_prompt"]


def test_request_confirmation_expense_phrasing():
    state = _base_state(
        {
            "target_kind": "expense",
            "expense_id": EXPENSE_ID,
            "created_by_role": "ADMIN",
            "reversal_amount": "700.00",
            "reversal_description": "diesel refill",
            "reversal_occurred_date": "2026-07-25",
        }
    )
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Reverse expense" in prompt
    assert "700.00" in prompt
    assert "diesel refill" in prompt
    assert "YES" in prompt


def test_request_confirmation_transfer_phrasing():
    state = _base_state(
        {
            "target_kind": "transfer",
            "money_transaction_id": TRANSACTION_ID,
            "created_by_role": "FINANCE",
            "reversal_amount": "5000.00",
            "reversal_from_account_name": "Company Bank",
            "reversal_to_account_name": "Site Cash",
        }
    )
    state.update(build_draft(state))
    prompt = request_confirmation(state)["pending_prompt"]
    assert "Reverse transfer" in prompt
    assert "Company Bank" in prompt
    assert "Site Cash" in prompt
    assert "5000.00" in prompt
