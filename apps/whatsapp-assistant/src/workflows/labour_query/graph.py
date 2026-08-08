"""Builds the labour-query graph."""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import generate_labour_query_reply


def build_labour_query_graph() -> Any:
    """Compile the labour-query graph: START -> generate_labour_query_reply -> END.

    Straight through, like every other query graph: the answer is already
    resolved by the time the graph runs (seeded by the caller), so there is
    nothing to branch on and nothing to confirm.
    """
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("generate_labour_query_reply", generate_labour_query_reply)
    graph.add_edge(START, "generate_labour_query_reply")
    graph.add_edge("generate_labour_query_reply", END)

    return graph.compile()
