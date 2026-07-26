"""Account-balance-query and expense-query workflow graphs — real LangGraph
integration tests. Skipped automatically when ``langgraph`` isn't installed.
Mirrors test_expense_capture_graph.py / test_account_admin_graph.py.
"""

from __future__ import annotations

import pytest

pytest.importorskip("langgraph")

from workflows.account_balance_query.graph import build_account_balance_query_graph  # noqa: E402
from workflows.expense_query.graph import build_expense_query_graph  # noqa: E402

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _base_state(fields: dict) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": "finance.account_query",
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": None,
        "site_id": None,
        "collected_fields": fields,
    }


async def test_balance_query_graph_runs_end_to_end():
    graph = build_account_balance_query_graph()

    result = await graph.ainvoke(
        _base_state({"balance_results": [{"name": "Site Cash", "balance": "3800.00"}]})
    )

    assert result.get("draft_action") is None
    assert "Site Cash" in result["pending_prompt"]
    assert "3800" in result["pending_prompt"]


async def test_expense_query_graph_runs_end_to_end():
    graph = build_expense_query_graph()

    result = await graph.ainvoke(
        _base_state(
            {
                "expense_results": {
                    "total": "700.00",
                    "count": 1,
                    "date_range_label": "today",
                    "items": [{"amount": "700.00", "description": "diesel", "occurred_date": "2026-07-25"}],
                }
            }
        )
    )

    assert result.get("draft_action") is None
    assert "700" in result["pending_prompt"]
    assert "diesel" in result["pending_prompt"]
