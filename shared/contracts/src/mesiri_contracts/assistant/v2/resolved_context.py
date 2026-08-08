"""ResolvedContext.v2 — dual namespace: context IDs + canonical Control Plane UUIDs."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from mesiri_contracts.assistant.context_enums import ContextConfidence, ContextSource

from .uuid_scope import CanonicalUuid

CONTRACT_VERSION = "v2"


class ResolvedContextV2(BaseModel):
    """Operating context with both M4 context IDs and canonical UUID scope."""

    version: str = CONTRACT_VERSION

    correlation_id: str
    source_message_id: str
    causation_id: str | None = None
    conversation_id: str | None = None

    # Context Layer (authorization / membership lookups)
    context_organization_id: str
    context_user_id: str
    context_project_id: str | None = None
    context_site_id: str | None = None

    membership_id: str | None = None
    role_ids: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)

    # Control Plane (canonical — propagated downstream)
    organization_id: CanonicalUuid
    user_id: CanonicalUuid
    project_id: CanonicalUuid | None = None
    site_id: CanonicalUuid | None = None

    context_source: ContextSource = ContextSource.UNRESOLVED
    context_confidence: ContextConfidence = ContextConfidence.UNRESOLVED
    locale: str | None = None
    timezone: str | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _scope_pairs_present(self) -> ResolvedContextV2:
        if self.project_id is not None and self.context_project_id is None:
            raise ValueError("context_project_id required when project_id is set")
        if self.site_id is not None and self.context_site_id is None:
            raise ValueError("context_site_id required when site_id is set")
        return self
