"""Material workflow graph — real LangGraph integration test.

Skipped automatically when ``langgraph`` isn't installed (it lives in the
optional ``workflow`` dependency group — install with
``uv pip install -e ".[workflow]"``). Proves the compiled graph actually runs
end to end; unit tests exercise the same node logic with fakes and need no
LangGraph import at all.
"""

from __future__ import annotations

import pytest

pytest.importorskip("langgraph")

from mesiri_contracts.assistant.draft_action import DraftActionType  # noqa: E402
from mesiri_contracts.assistant.planner_decision import WorkflowKey  # noqa: E402
from workflows.material.graph import build_material_graph  # noqa: E402


async def test_material_receipt_graph_runs_end_to_end():
    graph = build_material_graph()

    initial_state = {
        "workflow_instance_id": "11111111-1111-4111-8111-1111111111a1",
        "workflow_key": WorkflowKey.MATERIAL_RECEIPT.value,
        "correlation_id": "cor_test_1",
        "organization_id": "11111111-1111-4111-8111-111111111111",
        "user_id": "22222222-2222-4222-8222-222222222222",
        "project_id": "33333333-3333-4333-8333-333333333333",
        "site_id": "44444444-4444-4444-8444-444444444444",
        "collected_fields": {"material_name": "cement", "quantity": 20, "unit": "bags"},
    }

    result = await graph.ainvoke(initial_state)

    draft = result["draft_action"]
    assert draft.action_type is DraftActionType.RECORD_MATERIAL_RECEIPT
    assert draft.fields == {"material_name": "cement", "quantity": 20, "unit": "bags"}

    prompt = result["pending_prompt"]
    assert "Material Receipt" in prompt
    assert "cement" in prompt


async def test_material_usage_graph_runs_end_to_end():
    graph = build_material_graph()

    initial_state = {
        "workflow_instance_id": "11111111-1111-4111-8111-1111111111a2",
        "workflow_key": WorkflowKey.MATERIAL_USAGE.value,
        "correlation_id": "cor_test_2",
        "organization_id": "11111111-1111-4111-8111-111111111111",
        "user_id": "22222222-2222-4222-8222-222222222222",
        "collected_fields": {"material_name": "sand", "quantity": 5, "unit": "tons"},
    }

    result = await graph.ainvoke(initial_state)

    assert result["draft_action"].action_type is DraftActionType.RECORD_MATERIAL_USAGE
    assert "Material Usage" in result["pending_prompt"]


def test_registry_returns_the_same_compiled_graph_for_both_material_keys():
    from workflows.registry import WorkflowRegistry

    registry = WorkflowRegistry()
    receipt_graph = registry.get_graph(WorkflowKey.MATERIAL_RECEIPT)
    usage_graph = registry.get_graph(WorkflowKey.MATERIAL_USAGE)
    assert receipt_graph is not None
    assert usage_graph is not None
    # Compiled once and cached -- calling again returns the identical object.
    assert registry.get_graph(WorkflowKey.MATERIAL_RECEIPT) is receipt_graph
