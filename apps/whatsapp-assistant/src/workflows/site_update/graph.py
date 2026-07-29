"""Builds the Activity Creation & Continuation workflow graph (Daily
Reporting module) -- WorkflowKey.SITE_UPDATE.

Merges what used to be two separate graphs/workflow keys (SITE_UPDATE and
ACTIVITY_CONTINUATION) into one, per docs/execution/
ACTIVITY_RESOLUTION_AND_CORRECTION_PLAN.md: whether a message starts a new
Activity or appends a Progress Update to an existing one is now decided by
`resolve_target` (workflows/site_update/matching.py's scorer against every
open activity), not by which CanonicalEventType/WorkflowKey the message
happened to route to. Fixes F1 (the old code picked a target by recency
alone, with no check that it matched what the message described) and F2 (a
continuation message with nothing open dead-ended instead of creating new
work).

The photo path (`img_site_update`) is still handled separately, outside any
graph -- #2 Batch Media wires it as a direct attach
(runtime/evidence_query.py, no draft/confirmation), since evidence is
unambiguous and never needs a YES/NO.

LangGraph is imported lazily -- the core test suite runs without it
installed (optional `workflow` dependency group). Compiled without a
checkpointer: WorkflowState.v1 (persisted via the repository port) is the
single durable source of truth, same as every other v1 graph.
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import _TARGET_SLOT_NAME, build_draft, request_confirmation, resolve_target


def _route_after_target_resolution(state: WorkflowGraphState) -> str:
    """Slot-specific, not a generic truthy check -- same reasoning as every
    other multi-slot graph in this repo (e.g. expense_capture's
    `_route_after_account_resolution`): a stale awaiting_slot from
    somewhere else must never re-trigger this edge."""
    return "ask_slot" if state.get("awaiting_slot") == _TARGET_SLOT_NAME else "continue"


def build_activity_creation_graph() -> Any:
    """Compile the Activity Creation & Continuation graph:

    START -> resolve_target -> (ask_slot -> END | continue)
          -> build_draft -> request_confirmation -> END

    `resolve_target` either resolves outright (no open activities, one
    unambiguous match, or a memory-remembered activity already seeded by
    the caller) or sets `awaiting_slot`/`pending_prompt` and ends this pass
    there -- the same "ask and resume via provide_input()" shape
    expense_capture's `resolve_account` uses. `build_draft` then branches on
    whether `activity_id` ended up set: CREATE_ACTIVITY if not,
    ADD_PROGRESS_UPDATE if so.
    """
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("resolve_target", resolve_target)
    graph.add_node("build_draft", build_draft)
    graph.add_node("request_confirmation", request_confirmation)
    graph.add_edge(START, "resolve_target")
    graph.add_conditional_edges(
        "resolve_target",
        _route_after_target_resolution,
        {"ask_slot": END, "continue": "build_draft"},
    )
    graph.add_edge("build_draft", "request_confirmation")
    graph.add_edge("request_confirmation", END)
    return graph.compile()
