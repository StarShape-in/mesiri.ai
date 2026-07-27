"""Worker promotion workflow graph.

Two-pass structure -- the same ``offer_and_promote`` node handles both:

  START → offer_and_promote → [END, awaiting answer]
        → (re-entered with answer) → offer_and_promote → END

Pass 1  (no ``promotion_choice`` slot filled): builds the numbered list and
        pauses as COLLECTING_FIELDS.
Pass 2  (slot filled): parses selection, runs the final duplicate guard,
        creates workers for the selected ones, returns a confirmation text.
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import PROMOTION_SLOT, offer_and_promote


def _route(state: WorkflowGraphState) -> str:
    return "ask_slot" if state.get("awaiting_slot") == PROMOTION_SLOT else "done"


def build_worker_promotion_graph() -> Any:
    """Compile the Worker Promotion graph.

    START → offer_and_promote → ask_slot → END   (waiting for choice)
                              → done     → END   (after processing choice)
    """
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
