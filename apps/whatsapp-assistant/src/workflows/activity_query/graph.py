"""Builds the activity-search graph."""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import generate_activity_search_reply


def build_activity_query_graph() -> Any:
    """Compile the activity-search graph: START -> generate_activity_search_reply -> END.

    Straight through, like every other query graph: the answer is already
    resolved by the time the graph runs (seeded by the caller), so there is
    nothing to branch on and nothing to confirm.
    """
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("generate_activity_search_reply", generate_activity_search_reply)
    graph.add_edge(START, "generate_activity_search_reply")
    graph.add_edge("generate_activity_search_reply", END)

    return graph.compile()
