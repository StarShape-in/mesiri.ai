"""Builds the Expense Capture workflow graph.

Mirrors workflows/material/graph.py, extended by Finance Module Slice 1 with
a conditional branch for the "which account?" slot. Compiled without a
checkpointer: WorkflowState.v1 (persisted via the repository port) is the
single durable source of truth. LangGraph is imported lazily inside this
function — the core test suite runs without it installed (it lives in the
optional `workflow` dependency group).
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import build_draft, request_confirmation, resolve_account


def _route_after_account_resolution(state: WorkflowGraphState) -> str:
    return "ask_slot" if state.get("awaiting_slot") else "continue"


def build_expense_capture_graph() -> Any:
    """Compile the Expense Capture graph:

    START -> resolve_account -> (ask_slot -> END | build_draft -> request_confirmation -> END)

    `resolve_account` either resolves the paid-from choice outright (0 or 1
    real candidate) or sets `awaiting_slot`/`pending_prompt` and the graph
    ends there for this pass — WorkflowRuntime persists that as
    COLLECTING_FIELDS and re-invokes the graph via provide_input() once the
    user answers.
    """
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("resolve_account", resolve_account)
    graph.add_node("build_draft", build_draft)
    graph.add_node("request_confirmation", request_confirmation)
    graph.add_edge(START, "resolve_account")
    graph.add_conditional_edges(
        "resolve_account",
        _route_after_account_resolution,
        {"ask_slot": END, "continue": "build_draft"},
    )
    graph.add_edge("build_draft", "request_confirmation")
    graph.add_edge("request_confirmation", END)
    return graph.compile()
