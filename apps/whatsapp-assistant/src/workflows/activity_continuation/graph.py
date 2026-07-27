"""Builds the Activity Continuation workflow graph (Daily Reporting module).

Appends a Progress Update to an Activity already resolved by
runtime/inbound_journey.py's `_seed_open_activity` before this graph runs.
LangGraph is imported lazily -- the core test suite runs without it
installed (optional `workflow` dependency group). Compiled without a
checkpointer, same as every other v1 graph.

One conditional edge: `build_draft` either produces a draft (an activity was
found) or ends the pass with a clarifying message and no draft
(WorkflowKey.ACTIVITY_CONTINUATION is registered with
allows_completion_without_draft=True for exactly this outcome — see
workflows/registry.py). request_confirmation only runs when there is
something to confirm.
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import build_draft, request_confirmation


def _route_after_build_draft(state: WorkflowGraphState) -> str:
    return "confirm" if state.get("draft_action") is not None else "end"


def build_activity_continuation_graph() -> Any:
    """Compile the Activity Continuation graph:

    START -> build_draft -> (confirm -> request_confirmation -> END | end -> END)
    """
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("build_draft", build_draft)
    graph.add_node("request_confirmation", request_confirmation)
    graph.add_edge(START, "build_draft")
    graph.add_conditional_edges(
        "build_draft",
        _route_after_build_draft,
        {"confirm": "request_confirmation", "end": END},
    )
    graph.add_edge("request_confirmation", END)
    return graph.compile()
