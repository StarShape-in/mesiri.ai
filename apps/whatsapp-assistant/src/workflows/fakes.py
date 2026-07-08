"""In-memory fakes for the workflow layer — no DB, no LangGraph, no HTTP."""

from __future__ import annotations

from typing import Any

from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2


class FakeWorkflowInstanceRepository:
    """Deterministic in-memory WorkflowInstanceRepository for tests."""

    def __init__(self) -> None:
        self.saved: list[WorkflowStateV2] = []

    async def save(self, state: WorkflowStateV2) -> None:
        self.saved.append(state)


class FakeCompiledGraph:
    """Duck-typed stand-in for a compiled LangGraph graph — no LangGraph needed."""

    def __init__(self, result: dict[str, Any] | None = None, raise_error: bool = False) -> None:
        self._result = result
        self._raise = raise_error

    async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]:
        if self._raise:
            raise RuntimeError("boom")
        return {**state, **(self._result or {})}


class FakeWorkflowRegistry:
    """Duck-typed stand-in for WorkflowRegistry — no LangGraph needed."""

    def __init__(self, graphs: dict[WorkflowKey, FakeCompiledGraph] | None = None) -> None:
        self._graphs = graphs or {}

    def get_graph(self, key: WorkflowKey) -> FakeCompiledGraph | None:
        return self._graphs.get(key)
