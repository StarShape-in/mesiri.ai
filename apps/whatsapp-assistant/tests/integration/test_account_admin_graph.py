"""Account admin workflow graph — real LangGraph integration test.

Skipped automatically when ``langgraph`` isn't installed. Proves the
compiled graph actually runs end to end; unit tests exercise the same node
logic with fakes and need no LangGraph import at all. Mirrors
test_expense_capture_graph.py / test_material_graph.py.
"""

from __future__ import annotations

import pytest

pytest.importorskip("langgraph")

from mesiri_contracts.assistant.draft_action import DraftActionType  # noqa: E402
from workflows.account_admin.graph import build_account_admin_graph  # noqa: E402

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _base_state(fields: dict) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": "finance.account_admin",
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": None,
        "site_id": None,
        "collected_fields": fields,
    }


async def test_create_account_runs_end_to_end():
    graph = build_account_admin_graph()

    result = await graph.ainvoke(
        _base_state({"action": "create", "name": "Site Cash", "account_type": "cash"})
    )

    assert result["draft_action"].action_type is DraftActionType.MANAGE_MONEY_ACCOUNT
    assert result["draft_action"].fields["name"] == "Site Cash"
    assert "Create a new account" in result["pending_prompt"]
    assert "Site Cash" in result["pending_prompt"]


async def test_rename_account_runs_end_to_end():
    graph = build_account_admin_graph()

    result = await graph.ainvoke(
        _base_state({"action": "rename", "target_name": "Site Cash", "new_name": "Kochi Cash"})
    )

    assert "Rename" in result["pending_prompt"]
    assert "Kochi Cash" in result["pending_prompt"]


async def test_incomplete_ai_extraction_asks_instead_of_crashing_end_to_end():
    """Real LangGraph exercise of the conditional edge added 2026-07-26:
    AI extraction (unlike the deterministic parser, which always has every
    field by construction) can resolve `action` without the action-specific
    fields -- must route straight to END with a clarifying prompt, never
    reach request_confirmation with a half-built draft."""
    graph = build_account_admin_graph()

    result = await graph.ainvoke(_base_state({"action": "rename", "target_name": "Site Cash"}))

    assert result.get("draft_action") is None
    assert "new name" in result["pending_prompt"].lower()
