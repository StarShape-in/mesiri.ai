"""Builds the Transfer workflow graph.

Mirrors expense_capture's conditional shape (Finance Module Slice 1),
extended to two independent slots asked in sequence rather than one.
Compiled without a checkpointer: WorkflowState.v2 (persisted via the
repository port) is the single durable source of truth. LangGraph is
imported lazily inside this function — the core test suite runs without it
installed (optional `workflow` dependency group).
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import (
    _FROM_SLOT,
    _TO_SLOT,
    build_draft,
    request_confirmation,
    resolve_from_account,
    resolve_to_account,
)


def _route_after_from(state: WorkflowGraphState) -> str:
    """Slot-specific, not a generic truthy check: a stale awaiting_slot left
    over from a *previous* round asking about the OTHER slot (e.g. the user
    is now answering "to_account_id" while "from_account_id" was already
    resolved) must not make this edge re-ask the from-slot question."""
    return "ask_slot" if state.get("awaiting_slot") == _FROM_SLOT else "continue"


def _route_after_to(state: WorkflowGraphState) -> str:
    return "ask_slot" if state.get("awaiting_slot") == _TO_SLOT else "continue"


def build_transfer_graph() -> Any:
    """Compile the Transfer graph:

    START -> resolve_from_account -> (ask_slot -> END | continue)
          -> resolve_to_account -> (ask_slot -> END | continue)
          -> build_draft -> request_confirmation -> END
    """
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("resolve_from_account", resolve_from_account)
    graph.add_node("resolve_to_account", resolve_to_account)
    graph.add_node("build_draft", build_draft)
    graph.add_node("request_confirmation", request_confirmation)
    graph.add_edge(START, "resolve_from_account")
    graph.add_conditional_edges(
        "resolve_from_account",
        _route_after_from,
        {"ask_slot": END, "continue": "resolve_to_account"},
    )
    graph.add_conditional_edges(
        "resolve_to_account",
        _route_after_to,
        {"ask_slot": END, "continue": "build_draft"},
    )
    graph.add_edge("build_draft", "request_confirmation")
    graph.add_edge("request_confirmation", END)
    return graph.compile()
