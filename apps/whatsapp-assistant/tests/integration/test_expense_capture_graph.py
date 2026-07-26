"""Expense capture workflow graph — real LangGraph integration test.

Skipped automatically when ``langgraph`` isn't installed (optional
``workflow`` dependency group). Proves the compiled conditional-edge graph
(Finance Module Slice 1's "which account?" slot) actually runs end to end;
unit tests exercise the same node logic with fakes and need no LangGraph
import at all. Mirrors test_material_graph.py.
"""

from __future__ import annotations

import pytest

pytest.importorskip("langgraph")

from mesiri_contracts.assistant.draft_action import DraftActionType  # noqa: E402
from workflows.expense_capture.graph import build_expense_capture_graph  # noqa: E402

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"


def _base_state(fields: dict) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": "expense.submit",
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": PRJ,
        "site_id": None,
        "collected_fields": fields,
    }


async def test_zero_accounts_autofills_own_pocket_and_builds_draft_in_one_pass():
    graph = build_expense_capture_graph()

    result = await graph.ainvoke(_base_state({"amount": 250, "category": "fuel"}))

    assert result["draft_action"].action_type is DraftActionType.RECORD_EXPENSE
    assert result["draft_action"].fields["paid_from_own_pocket"] is True
    assert result.get("awaiting_slot") is None
    assert "Confirm this record" in result["pending_prompt"]


async def test_one_real_account_still_asks_since_own_pocket_is_always_an_option():
    graph = build_expense_capture_graph()

    result = await graph.ainvoke(
        _base_state(
            {
                "amount": 250,
                "account_candidates": [{"id": "a1", "name": "Site Cash"}],
            }
        )
    )

    assert result.get("draft_action") is None
    assert result["awaiting_slot"] == "account_id"
    assert "Site Cash" in result["pending_prompt"]
    assert "own pocket" in result["pending_prompt"].lower()


async def test_answering_the_slot_resumes_to_a_confirmable_draft():
    """Mirrors what WorkflowRuntime.provide_input() does: re-invoke the same
    graph with the prior collected_fields plus the raw answer text."""
    graph = build_expense_capture_graph()

    first_pass = await graph.ainvoke(
        _base_state(
            {
                "amount": 250,
                "account_candidates": [
                    {"id": "a1", "name": "Site Cash"},
                    {"id": "a2", "name": "Company Bank"},
                ],
            }
        )
    )
    assert first_pass["awaiting_slot"] == "account_id"

    second_state = _base_state(dict(first_pass["collected_fields"]))
    second_state["collected_fields"]["_slot_answer_text"] = "2"
    second_pass = await graph.ainvoke(second_state)

    assert second_pass.get("awaiting_slot") is None
    assert second_pass["draft_action"].fields["account_id"] == "a2"
    assert "Confirm this record" in second_pass["pending_prompt"]


async def test_no_duplicate_flag_skips_straight_to_a_confirmable_draft():
    """Finance Module Slice 8: the common case -- no likely duplicate --
    must not add an extra round trip."""
    graph = build_expense_capture_graph()

    result = await graph.ainvoke(_base_state({"amount": 250, "category": "fuel"}))

    assert result["draft_action"].action_type is DraftActionType.RECORD_EXPENSE
    assert result.get("awaiting_slot") is None
    assert "Confirm this record" in result["pending_prompt"]


async def test_duplicate_flagged_asks_then_yes_builds_the_draft():
    graph = build_expense_capture_graph()

    first_pass = await graph.ainvoke(
        _base_state({"amount": 250, "category": "fuel", "is_potential_duplicate": True})
    )
    assert first_pass.get("draft_action") is None
    assert first_pass["awaiting_slot"] == "duplicate_confirm"
    assert "duplicate" in first_pass["pending_prompt"]

    second_state = _base_state(dict(first_pass["collected_fields"]))
    second_state["awaiting_slot"] = "duplicate_confirm"
    second_state["collected_fields"]["_slot_answer_text"] = "yes"
    second_pass = await graph.ainvoke(second_state)

    assert second_pass["draft_action"].action_type is DraftActionType.RECORD_EXPENSE
    assert second_pass.get("awaiting_slot") is None
    assert "Confirm this record" in second_pass["pending_prompt"]
    # The plumbing flags never leak into the draft or the confirmation text.
    assert "is_potential_duplicate" not in second_pass["draft_action"].fields
    assert "duplicate_confirmed" not in second_pass["draft_action"].fields


async def test_duplicate_flagged_asks_then_no_cancels_with_no_draft():
    graph = build_expense_capture_graph()

    first_pass = await graph.ainvoke(
        _base_state({"amount": 250, "category": "fuel", "is_potential_duplicate": True})
    )
    assert first_pass["awaiting_slot"] == "duplicate_confirm"

    second_state = _base_state(dict(first_pass["collected_fields"]))
    second_state["awaiting_slot"] = "duplicate_confirm"
    second_state["collected_fields"]["_slot_answer_text"] = "no"
    second_pass = await graph.ainvoke(second_state)

    assert second_pass.get("draft_action") is None
    assert second_pass.get("awaiting_slot") is None
    assert "won't record" in second_pass["pending_prompt"]
