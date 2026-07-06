"""ResolvedContext.v1 — output contract of the Context module.

Produced by the Context resolver from ``NormalizedMessage`` +
``UnderstandingResult``. Captures who/where/what-state for downstream Planner
and workflow modules — but never workflow selection, business commands, or
persistence.

Ownership: SHARED ARCHITECTURE. Required reviewers: Alan + Ilan. Version: v1.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from mesiri_contracts.assistant.confidence import ConfidenceLevel

from .enums import ContextAmbiguityField, InteractionKind, UserRole, WorkflowKind, WorkflowPhase

CONTRACT_VERSION = "v1"


class ActorContext(BaseModel):
    """Resolved actor (user + organization + role)."""

    whatsapp_wa_id: str
    user_id: str | None = None
    organization_id: str | None = None
    role: UserRole | None = None
    display_name: str | None = None

    model_config = {"extra": "forbid"}


class ScopeContext(BaseModel):
    """Resolved project/site scope."""

    project_id: str | None = None
    project_name: str | None = None
    site_id: str | None = None
    site_name: str | None = None

    model_config = {"extra": "forbid"}


class WorkflowContext(BaseModel):
    """Snapshot of an active workflow instance (read-only, not selected here)."""

    workflow_instance_id: str
    workflow_kind: WorkflowKind | None = None
    phase: WorkflowPhase = WorkflowPhase.UNKNOWN

    model_config = {"extra": "forbid"}


class InteractionContext(BaseModel):
    """Snapshot of a pending human interaction."""

    interaction_id: str
    kind: InteractionKind = InteractionKind.UNKNOWN
    related_message_id: str | None = None

    model_config = {"extra": "forbid"}


class ReplyBindingContext(BaseModel):
    """Reply threading metadata interpreted by Context."""

    replied_to_message_id: str | None = None
    binds_to_prior_journey: bool = False

    model_config = {"extra": "forbid"}


class ContextAmbiguity(BaseModel):
    """One unresolved or conflicting context element."""

    field: ContextAmbiguityField
    reason: str
    candidates: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class ResolvedContext(BaseModel):
    """Canonical resolved business context for one inbound user journey."""

    version: str = CONTRACT_VERSION
    correlation_id: str
    source_message_id: str
    actor: ActorContext
    scope: ScopeContext
    workflow: WorkflowContext | None = None
    interaction: InteractionContext | None = None
    reply: ReplyBindingContext
    confidence: ConfidenceLevel = ConfidenceLevel.UNUSABLE
    ambiguities: list[ContextAmbiguity] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    resolved_at: datetime

    model_config = {"extra": "forbid"}
