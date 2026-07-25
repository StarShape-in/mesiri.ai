"""Ports the Workflow Runtime depends on.

The abstraction lives here, in the workflow layer — concrete adapters live in
infra (`backend/postgres/workflow_instance.py`). `workflows/` must never import
a repository type from `backend/`; this is the correct dependency direction
(infra implements the abstraction its consumer defines).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2


class SingleActiveConflict(Exception):
    """Raised by ``save`` when inserting would create a second
    AWAITING_CONFIRMATION instance for the same user (single-active invariant)."""


@dataclass(frozen=True, slots=True)
class LoadedWorkflowInstance:
    """A persisted workflow instance plus its optimistic-lock version.

    ``version`` is an infra concern kept out of the durable WorkflowStateV2
    contract; the runtime passes it back to ``transition`` to guard against
    concurrent modification (duplicate deliveries / simultaneous replies).
    """

    state: WorkflowStateV2
    version: int


class WorkflowInstanceRepository(Protocol):
    """Persists and transitions workflow instances. The concrete adapter is the
    only place permitted to touch SQL for workflow_instances."""

    async def save(self, state: WorkflowStateV2) -> None:
        """Insert a new instance. Must fail if it would create a second
        AWAITING_CONFIRMATION instance for the same user (single-active
        invariant — enforced by a partial unique index in Postgres)."""
        ...

    async def get_awaiting_confirmation(self, user_id: str) -> LoadedWorkflowInstance | None:
        """Return the user's single AWAITING_CONFIRMATION / active instance, or None."""
        ...

    async def get_awaiting_input(self, user_id: str) -> LoadedWorkflowInstance | None:
        """Return the user's single COLLECTING_FIELDS instance (mid-workflow
        slot-fill question, e.g. "which account?"), or None. Mirrors
        get_awaiting_confirmation -- there is no DB-level partial-unique
        guard for this phase (unlike AWAITING_CONFIRMATION), so the
        single-active property here rests on WorkflowRuntime's pre-check in
        start() rather than a hard constraint (see Finance Module Slice 1's
        plan doc for why that trade-off is acceptable for V1)."""
        ...

    async def transition(
        self, workflow_instance_id: str, expected_version: int, new_state: WorkflowStateV2
    ) -> bool:
        """Optimistic conditional update: apply ``new_state`` only if the row is
        still at ``expected_version``. Returns True if applied (rowcount 1),
        False if a concurrent transition already moved it (rowcount 0)."""
        ...
