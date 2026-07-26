"""Builds the Labour Attendance workflow graph.

Mirrors workflows/material/graph.py, with expense_capture's conditional
"ask a slot and end this pass" branch. Compiled without a checkpointer:
WorkflowState.v1 (persisted via the repository port) is the single durable
source of truth. LangGraph is imported lazily inside the builder — the core
test suite runs without it installed (it lives in the optional `workflow`
dependency group).

Only one conditional edge, despite Labour asking potentially many questions.
That is deliberate: `match_workers` is re-entrant and asks about one line per
pass (see nodes.py), so the *graph* never needs to know how many workers were
reported. Expressing "ask N times" as graph structure would require the shape
of the graph to depend on the message, which a compiled-once-and-cached
registry cannot do.
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import WORKER_MATCH_SLOT_PREFIX, build_draft, match_workers, request_confirmation


def _route_after_worker_matching(state: WorkflowGraphState) -> str:
    """Prefix-matched, not a generic truthy check — for the same reason
    expense_capture's `_route_after_account_resolution` is slot-specific: a
    stale `awaiting_slot` belonging to some other question must never
    re-trigger this edge. The prefix (rather than an exact name) is what lets
    one edge serve every worker line, since the slot name carries the line
    index."""
    return "ask_slot" if (state.get("awaiting_slot") or "").startswith(WORKER_MATCH_SLOT_PREFIX) else "continue"


def build_labour_attendance_graph() -> Any:
    """Compile the Labour Attendance graph:

    START -> match_workers -> (ask_slot -> END | continue)
          -> build_draft -> request_confirmation -> END

    `match_workers` resolves every named line it can — auto-matching the
    confident ones and marking the unrecognised ones as temporary workers —
    and either falls through with everything decided, or sets
    `awaiting_slot`/`pending_prompt` for the first genuinely ambiguous line
    and ends the pass there. The "ask" outcome persists as COLLECTING_FIELDS
    and re-invokes this same graph via `provide_input()` once the user
    answers, at which point the node applies the answer and continues from
    where it stopped.
    """
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("match_workers", match_workers)
    graph.add_node("build_draft", build_draft)
    graph.add_node("request_confirmation", request_confirmation)
    graph.add_edge(START, "match_workers")
    graph.add_conditional_edges(
        "match_workers",
        _route_after_worker_matching,
        {"ask_slot": END, "continue": "build_draft"},
    )
    graph.add_edge("build_draft", "request_confirmation")
    graph.add_edge("request_confirmation", END)
    return graph.compile()
