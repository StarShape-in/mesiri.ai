"""Builds the Site Issue Report workflow graph.

Mirrors workflows/material/graph.py's simplest shape: no conditional
branches, because issue_type/severity are closed enums the AI extraction
picks directly (nothing to resolve against a repository before the draft can
be shown, unlike Expense's account/duplicate/vendor slots). LangGraph is
imported lazily inside this function — the core test suite runs without it
installed (it lives in the optional `workflow` dependency group).
"""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState
from .nodes import build_draft, request_confirmation


def build_site_issue_report_graph() -> Any:
    """Compile the Site Issue Report graph: START -> build_draft -> request_confirmation -> END."""
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("build_draft", build_draft)
    graph.add_node("request_confirmation", request_confirmation)
    graph.add_edge(START, "build_draft")
    graph.add_edge("build_draft", "request_confirmation")
    graph.add_edge("request_confirmation", END)
    return graph.compile()
