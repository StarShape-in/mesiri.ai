"""Builds the expense-query graph."""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import generate_expense_query_reply


def build_expense_query_graph() -> Any:
    """Compile the expense-query graph: START -> generate_expense_query_reply -> END."""
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("generate_expense_query_reply", generate_expense_query_reply)
    graph.add_edge(START, "generate_expense_query_reply")
    graph.add_edge("generate_expense_query_reply", END)

    return graph.compile()
