"""Builds the Material workflow graph.

LangGraph is imported lazily inside this function — the core test suite runs
without it installed (it lives in the optional `workflow` dependency group).
Compiled without a checkpointer: WorkflowState.v1 (persisted via the
repository port) is the single durable source of truth for M6's straight-
through graph; there is no pause/resume inside LangGraph yet.
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import build_draft, request_confirmation


def build_material_graph() -> Any:
    """Compile the Material graph: START -> build_draft -> request_confirmation -> END."""
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("build_draft", build_draft)
    graph.add_node("request_confirmation", request_confirmation)
    graph.add_edge(START, "build_draft")
    graph.add_edge("build_draft", "request_confirmation")
    graph.add_edge("request_confirmation", END)
    return graph.compile()
