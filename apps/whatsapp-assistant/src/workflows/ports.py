"""Ports the Workflow Runtime depends on.

The abstraction lives here, in the workflow layer — concrete adapters live in
infra (`backend/postgres/workflow_instance.py`). `workflows/` must never import
a repository type from `backend/`; this is the correct dependency direction
(infra implements the abstraction its consumer defines).
"""

from __future__ import annotations

from typing import Protocol

from mesiri_contracts.assistant.workflow_state import WorkflowState


class WorkflowInstanceRepository(Protocol):
    """Persists a WorkflowState snapshot. The only place that may touch SQL for
    workflow_instances is the concrete adapter implementing this port."""

    async def save(self, state: WorkflowState) -> None: ...
