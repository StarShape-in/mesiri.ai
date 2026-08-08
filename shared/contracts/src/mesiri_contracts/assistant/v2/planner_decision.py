"""PlannerDecision.v2 — routing decision with canonical Control Plane UUID scope."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from mesiri_contracts.assistant.canonical_event import CanonicalEventType
from mesiri_contracts.assistant.planner_decision import (
    PlannerDecisionType,
    PlannerPriority,
    WorkflowKey,
)

from .uuid_scope import CanonicalUuid

CONTRACT_VERSION = "v2"


class PlannerDecisionV2(BaseModel):
    """Planner routing decision — canonical UUID scope only."""

    version: str = CONTRACT_VERSION

    correlation_id: str
    source_message_id: str
    causation_event_id: str | None = None

    decision_type: PlannerDecisionType
    workflow_key: WorkflowKey | None = None
    reason: CanonicalEventType
    priority: PlannerPriority = PlannerPriority.NORMAL

    organization_id: CanonicalUuid
    user_id: CanonicalUuid
    project_id: CanonicalUuid | None = None
    site_id: CanonicalUuid | None = None

    missing_fields: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _workflow_key_matches_decision_type(self) -> PlannerDecisionV2:
        if self.decision_type is PlannerDecisionType.START_WORKFLOW and self.workflow_key is None:
            raise ValueError("workflow_key is required when decision_type is START_WORKFLOW")
        if (
            self.decision_type is not PlannerDecisionType.START_WORKFLOW
            and self.workflow_key is not None
        ):
            raise ValueError("workflow_key must be None unless decision_type is START_WORKFLOW")
        return self
