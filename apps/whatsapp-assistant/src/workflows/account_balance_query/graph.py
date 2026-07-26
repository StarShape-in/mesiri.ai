"""Builds the account-balance-query graph."""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import generate_balance_reply


def build_account_balance_query_graph() -> Any:
    """Compile the balance-query graph: START -> generate_balance_reply -> END."""
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("generate_balance_reply", generate_balance_reply)
    graph.add_edge(START, "generate_balance_reply")
    graph.add_edge("generate_balance_reply", END)

    return graph.compile()
