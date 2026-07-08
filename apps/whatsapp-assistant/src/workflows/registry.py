"""Workflow Registry — the lookup layer between Planner and LangGraph.

Planner never imports a workflow engine or a specific graph (architecture rule
#10); it returns only a workflow_key. This registry resolves that key to a
compiled graph. Graphs are compiled once and cached — a WhatsApp message must
never trigger a graph recompilation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mesiri_contracts.assistant.planner_decision import WorkflowKey

from .material import build_material_graph

_BUILDERS: dict[WorkflowKey, Callable[[], Any]] = {
    WorkflowKey.MATERIAL_RECEIPT: build_material_graph,
    WorkflowKey.MATERIAL_USAGE: build_material_graph,
}


class WorkflowRegistry:
    """Resolves a WorkflowKey to a compiled graph, compiling (and caching) on first use."""

    def __init__(self) -> None:
        self._compiled: dict[WorkflowKey, Any] = {}

    def get_graph(self, key: WorkflowKey) -> Any | None:
        """Return the compiled graph for ``key``, or None if unmapped.

        Compiled exactly once per key for the lifetime of this registry —
        callers must not construct a new WorkflowRegistry per message.
        """
        if key in self._compiled:
            return self._compiled[key]
        builder = _BUILDERS.get(key)
        if builder is None:
            return None
        graph = builder()
        self._compiled[key] = graph
        return graph
