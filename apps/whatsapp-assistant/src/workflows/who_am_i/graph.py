"""Builds the WHO_AM_I identity lookup workflow graph."""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import generate_identity_reply


def build_who_am_i_graph() -> Any:
    """Compile the Who Am I graph: START -> generate_identity_reply -> END."""
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("generate_identity_reply", generate_identity_reply)
    graph.add_edge(START, "generate_identity_reply")
    graph.add_edge("generate_identity_reply", END)
    
    return graph.compile()
