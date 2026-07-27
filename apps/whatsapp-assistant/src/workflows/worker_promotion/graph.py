"""Worker promotion workflow graph.

One re-entrant node, re-invoked from scratch on each inbound message (the
graph is compiled without a checkpointer, like every other workflow here):

  START → offer_and_promote → END

``offer_and_promote`` decides which pass it is on from ``awaiting_slot`` --
the offer, the duplicate-check question, or the final write. See nodes.py.
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import DUPLICATE_SLOT, PROMOTION_SLOT, offer_and_promote


def _route(state: WorkflowGraphState) -> str:
    """Whether the node parked another question or finished."""
    return (
        "ask_slot"
        if state.get("awaiting_slot") in (PROMOTION_SLOT, DUPLICATE_SLOT)
        else "done"
    )


def build_worker_promotion_graph() -> Any:
    """Compile the Worker Promotion graph."""
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("offer_and_promote", offer_and_promote)
    graph.add_edge(START, "offer_and_promote")
    graph.add_conditional_edges(
        "offer_and_promote",
        _route,
        {"ask_slot": END, "done": END},
    )
    return graph.compile()
