"""Builds the Add Project Member workflow graph.

Mirrors workflows/site_create/graph.py exactly: build_draft has two outcomes
(a real draft, or a clarifying reply with none at all when the project
wasn't resolved or the member name wasn't extracted), so this needs the same
conditional edge. Compiled without a checkpointer: WorkflowState.v2
(persisted via the repository port) is the single durable source of truth.
LangGraph is imported lazily inside this function — the core test suite runs
without it installed (optional `workflow` dependency group).
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import build_draft, request_confirmation


def _route_after_build_draft(state: WorkflowGraphState) -> str:
    return "confirm" if state.get("draft_action") is not None else "done"


def build_add_project_member_graph() -> Any:
    """Compile the Add Project Member graph:

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
