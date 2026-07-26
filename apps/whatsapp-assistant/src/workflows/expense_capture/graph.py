"""Builds the Expense Capture workflow graph.

Mirrors workflows/material/graph.py, extended by Finance Module Slice 1 with
a conditional branch for the "which account?" slot, and by Slice 8 with a
"looks like a duplicate, record anyway?" gate. Compiled without a
checkpointer: WorkflowState.v1 (persisted via the repository port) is the
single durable source of truth. LangGraph is imported lazily inside this
function — the core test suite runs without it installed (it lives in the
optional `workflow` dependency group).
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import (
    _ACCOUNT_SLOT_NAME,
    _DUPLICATE_SLOT_NAME,
    _VENDOR_SLOT_NAME,
    build_draft,
    check_duplicate,
    request_confirmation,
    resolve_account,
    resolve_vendor,
)


def _route_after_account_resolution(state: WorkflowGraphState) -> str:
    """Slot-specific, not a generic truthy check: with two slots now sharing
    this graph (account_id, duplicate_confirm), a stale awaiting_slot left
    over from resuming the *other* one must not re-trigger this edge --
    exactly the routing bug Finance Module Slice 3 found and fixed for
    transfer's two-slot chain (see workflows/transfer/graph.py)."""
    return "ask_slot" if state.get("awaiting_slot") == _ACCOUNT_SLOT_NAME else "continue"


def _route_after_duplicate_check(state: WorkflowGraphState) -> str:
    if state.get("awaiting_slot") == _DUPLICATE_SLOT_NAME:
        return "ask_slot"
    if (state.get("collected_fields") or {}).get("duplicate_confirmed") == "no":
        return "cancelled"
    return "continue"


def _route_after_vendor_resolution(state: WorkflowGraphState) -> str:
    """Same stale-awaiting_slot guard as the two routers above -- with three
    slots now sharing this graph, only a "no" answered specifically for
    vendor_confirm should end this pass. Unlike duplicate, "no" here never
    cancels the record (see nodes.py's `resolve_vendor` docstring)."""
    return "ask_slot" if state.get("awaiting_slot") == _VENDOR_SLOT_NAME else "continue"


def build_expense_capture_graph() -> Any:
    """Compile the Expense Capture graph:

    START -> resolve_account -> (ask_slot -> END | continue)
          -> check_duplicate -> (ask_slot -> END | cancelled -> END | continue)
          -> resolve_vendor -> (ask_slot -> END | continue)
          -> build_draft -> request_confirmation -> END

    `resolve_account` either resolves the paid-from choice outright (0 or 1
    real candidate) or sets `awaiting_slot`/`pending_prompt` and the graph
    ends there for this pass. `check_duplicate` only asks when the caller
    flagged a likely duplicate (Finance Module Slice 8); a "no" answer ends
    the workflow with no draft at all (see nodes.py's `check_duplicate` and
    workflows/runtime.py's `_INFORMATIONAL_WORKFLOW_KEYS`, which allows
    EXPENSE_SUBMIT to complete without a draft for exactly this case).
    `resolve_vendor` only asks when the caller flagged the vendor name as
    unmatched; unlike check_duplicate, its "no" answer never ends the
    workflow -- it drops the vendor from the draft and continues to
    build_draft, so an unrecognized vendor never blocks recording the
    expense. All three "ask" outcomes persist as COLLECTING_FIELDS and
    re-invoke the graph via provide_input() once the user answers.
    """
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("resolve_account", resolve_account)
    graph.add_node("check_duplicate", check_duplicate)
    graph.add_node("resolve_vendor", resolve_vendor)
    graph.add_node("build_draft", build_draft)
    graph.add_node("request_confirmation", request_confirmation)
    graph.add_edge(START, "resolve_account")
    graph.add_conditional_edges(
        "resolve_account",
        _route_after_account_resolution,
        {"ask_slot": END, "continue": "check_duplicate"},
    )
    graph.add_conditional_edges(
        "check_duplicate",
        _route_after_duplicate_check,
        {"ask_slot": END, "cancelled": END, "continue": "resolve_vendor"},
    )
    graph.add_conditional_edges(
        "resolve_vendor",
        _route_after_vendor_resolution,
        {"ask_slot": END, "continue": "build_draft"},
    )
    graph.add_edge("build_draft", "request_confirmation")
    graph.add_edge("request_confirmation", END)
    return graph.compile()
