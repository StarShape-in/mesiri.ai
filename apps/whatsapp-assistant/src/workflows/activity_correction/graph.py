"""Builds the Activity Quantity Correction workflow graph (ADR-D14,
docs/execution/DAILY_REPORTING_PLAN.md) -- WorkflowKey.ACTIVITY_CORRECTION.

Two nodes only, mirroring workflows/reverse/graph.py's shape: no
slot-filling needed since the target is fully resolved by seeding before
this graph runs (workflows/activity_correction/nodes.py's module
docstring), and there is at most one candidate (same-session scoping,
ADR-D15's reasoning applied to correction too). `build_draft` has two
outcomes -- a real draft, or a "nothing to correct" reply with none at all
-- so one conditional edge, same as Reverse's.

LangGraph is imported lazily -- the core test suite runs without it
installed (optional `workflow` dependency group). Compiled without a
checkpointer: WorkflowState.v2 (persisted via the repository port) is the
single durable source of truth, same as every other v1/v2 graph.
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import build_draft, request_confirmation


def _route_after_build_draft(state: WorkflowGraphState) -> str:
    return "confirm" if state.get("draft_action") is not None else "done"


def build_activity_correction_graph() -> Any:
    """Compile the Activity Correction graph:

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
