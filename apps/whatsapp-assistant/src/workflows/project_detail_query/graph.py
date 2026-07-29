"""Builds the Project Detail Query workflow graph.

Straight through, like every other query graph (see
workflows/activity_query/graph.py): the answer is already resolved by the
time the graph runs (seeded by the caller), so there is nothing to branch
on and nothing to confirm.
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import generate_project_detail_reply


def build_project_detail_query_graph() -> Any:
    """Compile the project-detail-query graph:
    START -> generate_project_detail_reply -> END.
    """
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("generate_project_detail_reply", generate_project_detail_reply)
    graph.add_edge(START, "generate_project_detail_reply")
    graph.add_edge("generate_project_detail_reply", END)

    return graph.compile()
