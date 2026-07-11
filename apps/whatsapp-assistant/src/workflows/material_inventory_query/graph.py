"""Builds the material inventory-query graph."""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import generate_inventory_reply


def build_material_inventory_query_graph() -> Any:
    """Compile the inventory-query graph: START -> generate_inventory_reply -> END."""
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("generate_inventory_reply", generate_inventory_reply)
    graph.add_edge(START, "generate_inventory_reply")
    graph.add_edge("generate_inventory_reply", END)

    return graph.compile()
