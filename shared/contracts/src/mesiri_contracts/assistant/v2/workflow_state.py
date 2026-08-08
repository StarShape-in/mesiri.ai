"""WorkflowState.v2 — durable workflow snapshot with canonical Control Plane UUID scope."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.context.enums import WorkflowPhase

from .draft_action import DraftActionV2
from .uuid_scope import CanonicalUuid

CONTRACT_VERSION = "v2"


class WorkflowStateV2(BaseModel):
    """Durable snapshot of one running workflow instance."""

    version: str = CONTRACT_VERSION

    workflow_instance_id: str
    workflow_key: WorkflowKey
    correlation_id: str

    organization_id: CanonicalUuid
    user_id: CanonicalUuid
    project_id: CanonicalUuid | None = None
    site_id: CanonicalUuid | None = None

    phase: WorkflowPhase = WorkflowPhase.ACTIVE
    collected_fields: dict[str, Any] = Field(default_factory=dict)
    draft_action: DraftActionV2 | None = None
    pending_prompt: str | None = None
    # Name of the single-choice field a COLLECTING_FIELDS instance is waiting
    # on (e.g. "account_id") -- None once resolved or for phases that never
    # ask a mid-workflow question. See workflows/slots.py.
    awaiting_slot: str | None = None

    model_config = {"extra": "forbid"}
