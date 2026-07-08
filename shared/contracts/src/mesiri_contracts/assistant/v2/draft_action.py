"""DraftAction.v2 — proposed business action with canonical Control Plane UUID scope."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from mesiri_contracts.assistant.draft_action import DraftActionType

from .uuid_scope import CanonicalUuid

CONTRACT_VERSION = "v2"


class DraftActionV2(BaseModel):
    """Proposed business action awaiting confirmation — canonical UUID scope only."""

    version: str = CONTRACT_VERSION

    draft_id: str
    correlation_id: str
    causation_event_id: str | None = None
    workflow_instance_id: str

    action_type: DraftActionType

    organization_id: CanonicalUuid
    user_id: CanonicalUuid
    project_id: CanonicalUuid | None = None
    site_id: CanonicalUuid | None = None

    fields: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}
