"""Context module port interfaces and port-side DTOs (read-only).

Adapters implement these protocols; the Context resolver depends on the
interfaces only — never on PostgreSQL, Redis, or infrastructure SDKs.

Ownership: SHARED ARCHITECTURE (interfaces). Adapter implementations: TBD.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from .enums import InteractionKind, UserRole, WorkflowKind, WorkflowPhase


class IdentityRecord(BaseModel):
    """Actor identity resolved from a channel identifier (e.g. WhatsApp wa_id)."""

    user_id: str
    organization_id: str | None = None
    role: UserRole
    display_name: str | None = None
    whatsapp_wa_id: str

    model_config = {"extra": "forbid"}


class ScopeRecord(BaseModel):
    """Project/site scope resolved for an authenticated actor."""

    project_id: str | None = None
    project_name: str | None = None
    site_id: str | None = None
    site_name: str | None = None

    model_config = {"extra": "forbid"}


class ActiveWorkflowSnapshot(BaseModel):
    """Read-only view of an in-flight workflow instance."""

    workflow_instance_id: str
    workflow_kind: WorkflowKind | None = None
    phase: WorkflowPhase = WorkflowPhase.UNKNOWN

    model_config = {"extra": "forbid"}


class PendingInteractionSnapshot(BaseModel):
    """Read-only view of a pending human-in-the-loop interaction."""

    interaction_id: str
    kind: InteractionKind = InteractionKind.UNKNOWN
    related_message_id: str | None = None

    model_config = {"extra": "forbid"}


@runtime_checkable
class IdentityLookupPort(Protocol):
    """Resolve user, organization, and role from a WhatsApp identity."""

    async def resolve_by_whatsapp(
        self,
        wa_id: str,
        *,
        correlation_id: str,
    ) -> IdentityRecord | None: ...


@runtime_checkable
class ScopeLookupPort(Protocol):
    """Resolve project/site scope for an authenticated actor."""

    async def resolve_default_scope(
        self,
        user_id: str,
        organization_id: str,
        *,
        correlation_id: str,
    ) -> ScopeRecord | None: ...

    async def resolve_by_reply(
        self,
        replied_to_message_id: str,
        *,
        correlation_id: str,
    ) -> ScopeRecord | None: ...


@runtime_checkable
class WorkflowStateReadPort(Protocol):
    """Read-only access to active workflow and pending interaction state.

    Narrower than the future Memory module: Context only needs workflow-state
    snapshots, not conversation history or semantic retrieval.
    """

    async def get_active_workflow(
        self,
        user_id: str,
        *,
        correlation_id: str,
    ) -> ActiveWorkflowSnapshot | None: ...

    async def get_pending_interaction(
        self,
        user_id: str,
        *,
        correlation_id: str,
    ) -> PendingInteractionSnapshot | None: ...
