"""Builds the Activity Creation workflow graph (Daily Reporting module).

Fills the gap docs/execution/DAILY_REPORTING_PLAN.md's §2.1 identified:
`WorkflowKey.SITE_UPDATE` was routed (planner/routing.py) and extracted for
(the `general_site_update` AI slot) but had no compiled graph. This is that
graph, for the text/voice path. The photo path (`img_site_update`) is
handled separately, outside any graph -- #2 Batch Media wires it as a
direct attach (runtime/evidence_query.py, no draft/confirmation, see
AttachEvidenceCommand's docstring) rather than routing photos through this
graph, since evidence is unambiguous and never needs a YES/NO.

LangGraph is imported lazily -- the core test suite runs without it
installed (optional `workflow` dependency group). Compiled without a
checkpointer: WorkflowState.v1 (persisted via the repository port) is the
single durable source of truth, same as every other v1 graph.

Two nodes only, mirroring workflows/material/graph.py rather than Labour's
multi-slot loop -- P10 means no mid-workflow disambiguation question is
needed in V1: location/work-package resolution is a resolution-gate concern
that runs *before* this graph (plan §1B.2), not inside it.
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import build_draft, request_confirmation


def build_activity_creation_graph() -> Any:
    """Compile the Activity Creation graph:
    START -> build_draft -> request_confirmation -> END."""
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("build_draft", build_draft)
    graph.add_node("request_confirmation", request_confirmation)
    graph.add_edge(START, "build_draft")
    graph.add_edge("build_draft", "request_confirmation")
    graph.add_edge("request_confirmation", END)
    return graph.compile()
