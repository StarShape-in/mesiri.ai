"""Builds the Account Admin workflow graph.

No slot-filling, but (since 2026-07-26, when AI extraction became a second
producer alongside the deterministic command parser -- see nodes.py's
module docstring) `build_draft` has two outcomes: a real draft, or a
clarifying reply with none at all when the action-specific fields weren't
extracted -- same shape as workflows/reverse/graph.py's "nothing to
reverse" branch, so this needs the same conditional edge. Compiled without
a checkpointer: WorkflowState.v2 (persisted via the repository port) is the
single durable source of truth. LangGraph is imported lazily inside this
function — the core test suite runs without it installed (optional
`workflow` dependency group).
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import build_draft, request_confirmation


def _route_after_build_draft(state: WorkflowGraphState) -> str:
    return "confirm" if state.get("draft_action") is not None else "done"


def build_account_admin_graph() -> Any:
    """Compile the Account Admin graph:

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
