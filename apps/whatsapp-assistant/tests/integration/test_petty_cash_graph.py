"""Petty cash workflow graph — real LangGraph integration test.

Skipped automatically when ``langgraph`` isn't installed. Proves the
compiled single-slot conditional-edge graph (Finance Module Slice 5) runs
end to end for both directions, including the ask -> answer -> confirm
round trip. Mirrors test_transfer_graph.py.
"""

from __future__ import annotations

import pytest

pytest.importorskip("langgraph")

from mesiri_contracts.assistant.draft_action import DraftActionType  # noqa: E402
from workflows.petty_cash.graph import build_petty_cash_graph  # noqa: E402

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
ACC_A = "aaaaaaaa-1111-4111-8111-111111111111"
ACC_B = "bbbbbbbb-2222-4222-8222-222222222222"
RECIPIENT_ACC = "cccccccc-3333-4333-8333-333333333333"


def _base_state(fields: dict) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": "finance.petty_cash",
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": None,
        "site_id": None,
        "collected_fields": fields,
    }


_CANDIDATES = [{"id": ACC_A, "name": "Company Bank"}, {"id": ACC_B, "name": "Site Cash"}]


async def test_issue_with_one_candidate_builds_draft_in_one_pass():
    graph = build_petty_cash_graph()

    result = await graph.ainvoke(
        _base_state(
            {
                "amount": 20000,
                "direction": "issue",
                "recipient_name": "Alan",
                "recipient_account_id": RECIPIENT_ACC,
                "recipient_account_name": "Alan — Petty Cash",
                "account_candidates": [_CANDIDATES[0]],
            }
        )
    )

    assert result["draft_action"].action_type is DraftActionType.TRANSFER_MONEY
    assert result["draft_action"].fields["from_account_id"] == ACC_A
    assert result["draft_action"].fields["to_account_id"] == RECIPIENT_ACC
    assert result.get("awaiting_slot") is None
    assert "Confirm this petty cash issuance" in result["pending_prompt"]
    assert "Alan — Petty Cash" in result["pending_prompt"]


async def test_issue_with_multiple_candidates_asks_then_confirms():
    graph = build_petty_cash_graph()

    first_pass = await graph.ainvoke(
        _base_state(
            {
                "amount": 20000,
                "direction": "issue",
                "recipient_name": "Alan",
                "recipient_account_id": RECIPIENT_ACC,
                "recipient_account_name": "Alan — Petty Cash",
                "account_candidates": _CANDIDATES,
            }
        )
    )
    assert first_pass["awaiting_slot"] == "from_account_id"
    assert first_pass.get("draft_action") is None

    second_state = _base_state(dict(first_pass["collected_fields"]))
    second_state["awaiting_slot"] = "from_account_id"
    second_state["collected_fields"]["_slot_answer_text"] = "2"
    second_pass = await graph.ainvoke(second_state)

    assert second_pass.get("awaiting_slot") is None
    assert second_pass["draft_action"].fields["from_account_id"] == ACC_B
    assert second_pass["draft_action"].fields["to_account_id"] == RECIPIENT_ACC
    assert "Confirm this petty cash issuance" in second_pass["pending_prompt"]


async def test_return_prefills_from_and_asks_to_then_confirms():
    graph = build_petty_cash_graph()

    first_pass = await graph.ainvoke(
        _base_state(
            {
                "amount": 3000,
                "direction": "return",
                "recipient_name": "Alan",
                "recipient_account_id": RECIPIENT_ACC,
                "recipient_account_name": "Alan — Petty Cash",
                "account_candidates": _CANDIDATES,
            }
        )
    )
    assert first_pass["awaiting_slot"] == "to_account_id"
    assert first_pass["collected_fields"]["from_account_id"] == RECIPIENT_ACC

    second_state = _base_state(dict(first_pass["collected_fields"]))
    second_state["awaiting_slot"] = "to_account_id"
    second_state["collected_fields"]["_slot_answer_text"] = "Company Bank"
    second_pass = await graph.ainvoke(second_state)

    assert second_pass.get("awaiting_slot") is None
    assert second_pass["draft_action"].fields["from_account_id"] == RECIPIENT_ACC
    assert second_pass["draft_action"].fields["to_account_id"] == ACC_A
    assert "Confirm this petty cash return" in second_pass["pending_prompt"]
