"""Transfer workflow graph — real LangGraph integration test.

Skipped automatically when ``langgraph`` isn't installed. Proves the
compiled two-slot conditional-edge graph (Finance Module Slice 3) actually
runs end to end, including the full ask-from -> answer -> ask-to -> answer
-> confirm round trip. Mirrors test_expense_capture_graph.py.
"""

from __future__ import annotations

import pytest

pytest.importorskip("langgraph")

from mesiri_contracts.assistant.draft_action import DraftActionType  # noqa: E402
from workflows.transfer.graph import build_transfer_graph  # noqa: E402

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
ACC_A = "aaaaaaaa-1111-4111-8111-111111111111"
ACC_B = "bbbbbbbb-2222-4222-8222-222222222222"
ACC_C = "cccccccc-3333-4333-8333-333333333333"


def _base_state(fields: dict) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": "finance.transfer",
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": None,
        "site_id": None,
        "collected_fields": fields,
    }


_CANDIDATES = [
    {"id": ACC_A, "name": "Company Bank"},
    {"id": ACC_B, "name": "Site Cash"},
    {"id": ACC_C, "name": "Petty Cash"},
]


async def test_both_names_resolve_builds_draft_in_one_pass():
    graph = build_transfer_graph()

    result = await graph.ainvoke(
        _base_state(
            {
                "amount": 5000,
                "from_account_name": "Company Bank",
                "to_account_name": "Site Cash",
                "account_candidates": _CANDIDATES,
            }
        )
    )

    assert result["draft_action"].action_type is DraftActionType.TRANSFER_MONEY
    assert result["draft_action"].fields["from_account_id"] == ACC_A
    assert result["draft_action"].fields["to_account_id"] == ACC_B
    assert result.get("awaiting_slot") is None
    assert "Confirm this transfer" in result["pending_prompt"]
    assert "Company Bank" in result["pending_prompt"]
    assert "Site Cash" in result["pending_prompt"]


async def test_no_names_asks_from_then_to_then_confirms():
    graph = build_transfer_graph()

    first_pass = await graph.ainvoke(
        _base_state({"amount": 5000, "account_candidates": _CANDIDATES})
    )
    assert first_pass["awaiting_slot"] == "from_account_id"
    assert first_pass.get("draft_action") is None

    second_state = _base_state(dict(first_pass["collected_fields"]))
    second_state["awaiting_slot"] = "from_account_id"
    second_state["collected_fields"]["_slot_answer_text"] = "1"
    second_pass = await graph.ainvoke(second_state)
    assert second_pass["awaiting_slot"] == "to_account_id"
    assert second_pass.get("draft_action") is None
    assert second_pass["collected_fields"]["from_account_id"] == ACC_A

    third_state = _base_state(dict(second_pass["collected_fields"]))
    third_state["awaiting_slot"] = "to_account_id"
    third_state["collected_fields"]["_slot_answer_text"] = "2"
    third_pass = await graph.ainvoke(third_state)

    assert third_pass.get("awaiting_slot") is None
    assert third_pass["draft_action"].fields["from_account_id"] == ACC_A
    # Candidate list for the "to" slot excludes the already-picked "from"
    # account, so "2" (second remaining candidate = Petty Cash) is ACC_C.
    assert third_pass["draft_action"].fields["to_account_id"] == ACC_C
    assert "Confirm this transfer" in third_pass["pending_prompt"]
