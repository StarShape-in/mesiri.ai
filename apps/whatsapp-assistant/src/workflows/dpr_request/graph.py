"""Builds the dpr-request graph."""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import generate_dpr_request_reply


def build_dpr_request_graph() -> Any:
    """Compile the dpr-request graph: START -> generate_dpr_request_reply -> END.

    Straight through, like every other query graph: the status is already
    resolved by the time the graph runs (seeded by the caller), so there is
    nothing to branch on and nothing to confirm.
    """
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("generate_dpr_request_reply", generate_dpr_request_reply)
    graph.add_edge(START, "generate_dpr_request_reply")
    graph.add_edge("generate_dpr_request_reply", END)

    return graph.compile()
