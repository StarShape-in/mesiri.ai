"""Fake read-only workflow-state adapter for Context resolver tests."""

from __future__ import annotations

from mesiri_contracts.common.errors import MesiriError
from mesiri_contracts.context.ports import ActiveWorkflowSnapshot, PendingInteractionSnapshot


class FakeWorkflowStateReadPort:
    """In-memory active workflow and pending interaction snapshots for tests."""

    def __init__(
        self,
        *,
        active_workflows: dict[str, ActiveWorkflowSnapshot | None] | None = None,
        pending_interactions: dict[str, PendingInteractionSnapshot | None] | None = None,
        fail_with: MesiriError | None = None,
    ) -> None:
        self._active_workflows = active_workflows or {}
        self._pending_interactions = pending_interactions or {}
        self.fail_with = fail_with

    def set_active_workflow(self, user_id: str, snapshot: ActiveWorkflowSnapshot | None) -> None:
        self._active_workflows[user_id] = snapshot

    def set_pending_interaction(
        self,
        user_id: str,
        snapshot: PendingInteractionSnapshot | None,
    ) -> None:
        self._pending_interactions[user_id] = snapshot

    async def get_active_workflow(
        self,
        user_id: str,
        *,
        correlation_id: str,
    ) -> ActiveWorkflowSnapshot | None:
        if self.fail_with is not None:
            raise self.fail_with
        return self._active_workflows.get(user_id)

    async def get_pending_interaction(
        self,
        user_id: str,
        *,
        correlation_id: str,
    ) -> PendingInteractionSnapshot | None:
        if self.fail_with is not None:
            raise self.fail_with
        return self._pending_interactions.get(user_id)
