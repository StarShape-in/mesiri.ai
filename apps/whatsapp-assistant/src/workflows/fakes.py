"""In-memory fakes for the workflow layer — no DB, no LangGraph, no HTTP."""

from __future__ import annotations

from typing import Any

from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2
from mesiri_contracts.context.enums import WorkflowPhase

from .ports import LoadedWorkflowInstance, SingleActiveConflict


class FakeWorkflowInstanceRepository:
    """Deterministic in-memory WorkflowInstanceRepository for tests.

    Mirrors the Postgres adapter's contract: version tracking for optimistic
    locking, the single-active-confirmation invariant on save, and a
    version-conditional transition.
    """

    def __init__(self) -> None:
        # workflow_instance_id -> (state, version)
        self._rows: dict[str, tuple[WorkflowStateV2, int]] = {}

    @property
    def saved(self) -> list[WorkflowStateV2]:
        return [state for state, _ in self._rows.values()]

    def seed(self, state: WorkflowStateV2, version: int = 0) -> None:
        """Test helper: place an existing instance without invariant checks."""
        self._rows[state.workflow_instance_id] = (state, version)

    async def save(self, state: WorkflowStateV2) -> None:
        if state.phase is WorkflowPhase.AWAITING_CONFIRMATION:
            for existing, _ in self._rows.values():
                if (
                    existing.user_id == state.user_id
                    and existing.phase is WorkflowPhase.AWAITING_CONFIRMATION
                ):
                    raise SingleActiveConflict(
                        f"user {state.user_id} already has an awaiting-confirmation workflow"
                    )
        self._rows[state.workflow_instance_id] = (state, 0)

    async def get_awaiting_confirmation(self, user_id: str) -> LoadedWorkflowInstance | None:
        for state, version in self._rows.values():
            if state.user_id == user_id and state.phase is WorkflowPhase.AWAITING_CONFIRMATION:
                return LoadedWorkflowInstance(state=state, version=version)
        return None

    async def transition(
        self, workflow_instance_id: str, expected_version: int, new_state: WorkflowStateV2
    ) -> bool:
        row = self._rows.get(workflow_instance_id)
        if row is None:
            return False
        _, version = row
        if version != expected_version:
            return False
        self._rows[workflow_instance_id] = (new_state, version + 1)
        return True


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
