"""Builds the Site Issue Close-out workflow graph.

Mirrors workflows/reverse/graph.py: build_draft has two outcomes -- a real
draft, or a "nothing to close" reply with none at all -- so this graph
needs one conditional edge, unlike site_issue_report's plain 2-node chain.
LangGraph is imported lazily inside this function — the core test suite
runs without it installed (optional `workflow` dependency group).
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import build_draft, request_confirmation


def _route_after_build_draft(state: WorkflowGraphState) -> str:
    return "confirm" if state.get("draft_action") is not None else "done"


def build_site_issue_close_graph() -> Any:
    """Compile the Site Issue Close-out graph:

    START -> build_draft -> (confirm -> request_confirmation -> END | done -> END)
    """
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("build_draft", build_draft)
    graph.add_node("request_confirmation", request_confirmation)
    graph.add_edge(START, "build_draft")
    graph.add_conditional_edges(
        "build_draft", _route_after_build_draft, {"confirm": "request_confirmation", "done": END}
    )
    graph.add_edge("request_confirmation", END)
    return graph.compile()
