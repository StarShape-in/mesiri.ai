"""Builds the Create User workflow graph.

resolve_whatsapp_number runs first (Finance Module Slice 1's slot-fill
pattern, mirroring expense_capture/graph.py's resolve_account edge exactly)
so a missing/invalid number leaves a real, resumable COLLECTING_FIELDS
state instead of terminating -- see nodes.py's resolve_whatsapp_number
docstring for the live bug this fixes (a lost phone number reply, confirmed
by trace). build_draft then has two outcomes as before (a real draft, or a
clarifying reply with none at all when the name wasn't extracted), needing
the same conditional edge it always had. Compiled without a checkpointer:
WorkflowState.v2 (persisted via the repository port) is the single durable
source of truth. LangGraph is imported lazily inside this function — the
core test suite runs without it installed (optional `workflow` dependency
group).
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import (
    _NUMBER_SLOT_NAME,
    build_draft,
    request_confirmation,
    resolve_whatsapp_number,
)


def _route_after_number_resolution(state: WorkflowGraphState) -> str:
    return "ask_slot" if state.get("awaiting_slot") == _NUMBER_SLOT_NAME else "continue"


def _route_after_build_draft(state: WorkflowGraphState) -> str:
    return "confirm" if state.get("draft_action") is not None else "done"


def build_create_user_graph() -> Any:
    """Compile the Create User graph:

    START -> resolve_whatsapp_number -> (ask_slot -> END | continue)
          -> build_draft -> (confirm -> request_confirmation -> END | done -> END)
    """
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("resolve_whatsapp_number", resolve_whatsapp_number)
    graph.add_node("build_draft", build_draft)
    graph.add_node("request_confirmation", request_confirmation)
    graph.add_edge(START, "resolve_whatsapp_number")
    graph.add_conditional_edges(
        "resolve_whatsapp_number",
        _route_after_number_resolution,
        {"ask_slot": END, "continue": "build_draft"},
    )
    graph.add_conditional_edges(
        "build_draft", _route_after_build_draft, {"confirm": "request_confirmation", "done": END}
    )
    graph.add_edge("request_confirmation", END)
    return graph.compile()
