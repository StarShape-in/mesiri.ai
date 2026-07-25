"""Builds the Account Admin workflow graph.

No slot-filling -- the deterministic command parser
(runtime/account_admin_parser.py) already extracted every field before the
graph runs, so this is the simplest v1 shape (mirrors workflows/material/
graph.py's original 2-node form, before expense_capture grew a conditional
branch). Compiled without a checkpointer: WorkflowState.v2 (persisted via
the repository port) is the single durable source of truth. LangGraph is
imported lazily inside this function — the core test suite runs without it
installed (optional `workflow` dependency group).
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import build_draft, request_confirmation


def build_account_admin_graph() -> Any:
    """Compile the Account Admin graph: START -> build_draft -> request_confirmation -> END."""
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("build_draft", build_draft)
    graph.add_node("request_confirmation", request_confirmation)
    graph.add_edge(START, "build_draft")
    graph.add_edge("build_draft", "request_confirmation")
    graph.add_edge("request_confirmation", END)
    return graph.compile()
