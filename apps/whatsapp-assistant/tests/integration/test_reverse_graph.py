"""Reverse workflow graph — real LangGraph integration test.

Skipped automatically when ``langgraph`` isn't installed. Proves the
compiled conditional-edge graph (Finance Module Slice 7) runs end to end
for both outcomes: a draft when a target is found, and a plain completed
reply with no draft when nothing is found to reverse. Mirrors
test_transfer_graph.py / test_petty_cash_graph.py.
"""

from __future__ import annotations

import pytest

pytest.importorskip("langgraph")

from mesiri_contracts.assistant.draft_action import DraftActionType  # noqa: E402
from workflows.reverse.graph import build_reverse_graph  # noqa: E402

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
EXPENSE_ID = "55555555-5555-4555-8555-555555555555"


def _base_state(fields: dict) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": "finance.reverse",
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": None,
        "site_id": None,
        "collected_fields": fields,
    }


async def test_found_expense_builds_draft_and_confirms():
    graph = build_reverse_graph()

    result = await graph.ainvoke(
        _base_state(
            {
                "target_kind": "expense",
                "expense_id": EXPENSE_ID,
                "created_by_role": "ADMIN",
                "reversal_amount": "700.00",
                "reversal_description": "diesel refill",
                "reversal_occurred_date": "2026-07-25",
            }
        )
    )

    assert result["draft_action"].action_type is DraftActionType.REVERSE_TRANSACTION
    assert result["draft_action"].fields["expense_id"] == EXPENSE_ID
    assert "Confirm this reversal" in result["pending_prompt"]
    assert "diesel refill" in result["pending_prompt"]


async def test_nothing_to_reverse_completes_without_a_draft():
    graph = build_reverse_graph()

    result = await graph.ainvoke(_base_state({"target_kind": "expense", "created_by_role": "ADMIN"}))

    assert result.get("draft_action") is None
    assert "no confirmed expenses" in result["pending_prompt"]
