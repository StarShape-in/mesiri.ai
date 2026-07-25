"""Builds the Petty Cash workflow graph.

Mirrors expense_capture's conditional shape (single slot, Finance Module
Slice 1), reused here for Slice 5 -- see nodes.py's module docstring for why
this graph still ends up building a plain DraftActionType.TRANSFER_MONEY
draft. Compiled without a checkpointer: WorkflowState.v2 (persisted via the
repository port) is the single durable source of truth. LangGraph is
imported lazily inside this function — the core test suite runs without it
installed (optional `workflow` dependency group).
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import build_draft, request_confirmation, resolve_other_account


def _route_after_account_resolution(state: WorkflowGraphState) -> str:
    return "ask_slot" if state.get("awaiting_slot") else "continue"


def build_petty_cash_graph() -> Any:
    """Compile the Petty Cash graph:

    START -> resolve_other_account -> (ask_slot -> END | build_draft -> request_confirmation -> END)
    """
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("resolve_other_account", resolve_other_account)
    graph.add_node("build_draft", build_draft)
    graph.add_node("request_confirmation", request_confirmation)
    graph.add_edge(START, "resolve_other_account")
    graph.add_conditional_edges(
        "resolve_other_account",
        _route_after_account_resolution,
        {"ask_slot": END, "continue": "build_draft"},
    )
    graph.add_edge("build_draft", "request_confirmation")
    graph.add_edge("request_confirmation", END)
    return graph.compile()
