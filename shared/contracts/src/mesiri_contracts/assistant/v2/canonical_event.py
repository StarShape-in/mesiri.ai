"""CanonicalEvent.v2 — business-intent signal with canonical Control Plane UUID scope."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from mesiri_contracts.assistant.canonical_event import (
    CanonicalEventType,
    IntentCompleteness,
)

from .uuid_scope import CanonicalUuid

CONTRACT_VERSION = "v2"


class CanonicalEventV2(BaseModel):
    """Normalized business intent for the Planner — canonical UUID scope only."""

    version: str = CONTRACT_VERSION

    event_id: str
    correlation_id: str
    source_message_id: str
    causation_id: str | None = None
    conversation_id: str | None = None

    event_type: CanonicalEventType
    completeness: IntentCompleteness

    organization_id: CanonicalUuid
    user_id: CanonicalUuid
    project_id: CanonicalUuid | None = None
    site_id: CanonicalUuid | None = None
    permissions: list[str] = Field(default_factory=list)

    fields: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
