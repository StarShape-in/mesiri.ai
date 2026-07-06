"""ResolvedContext.v1 — the M4 output contract.

Produced by the Context Foundation from a ``NormalizedMessage`` +
``UnderstandingResult``. It answers *who is speaking, which organization /
project / site the message belongs to, what they are allowed to do, where that
context came from, and how confident we are* — but never selects a workflow,
persists a business record, or converses with the user (all downstream).

Authoritative identity / membership / permission / project / site data always
originates in PostgreSQL. AI understanding contributes semantic *references*
only (e.g. a project name), never authoritative ids. Redis may supply an
*ephemeral active context* candidate, but it is always revalidated against
PostgreSQL authorization before it appears here.

Ownership: SHARED ARCHITECTURE — part of the M0 contract surface. Version: v1.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .context_enums import ContextConfidence, ContextSource

CONTRACT_VERSION = "v1"


class ResolvedContext(BaseModel):
    """The authoritative operating context for a single inbound message."""

    version: str = CONTRACT_VERSION

    # -- Provenance / linkage (correlation must survive end to end) ----------
    correlation_id: str
    source_message_id: str
    # The message whose resolution *caused* this context (causation linkage).
    causation_id: str | None = None
    conversation_id: str | None = None

    # -- Authoritative identity / tenancy (always from PostgreSQL) -----------
    organization_id: str
    user_id: str
    membership_id: str | None = None
    role_ids: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)

    # -- Resolved location (may be unresolved -> None) -----------------------
    project_id: str | None = None
    site_id: str | None = None

    # -- Why this context was selected + how sure we are ---------------------
    context_source: ContextSource = ContextSource.UNRESOLVED
    context_confidence: ContextConfidence = ContextConfidence.UNRESOLVED

    # -- User locale / timezone (best-effort, from preferences) --------------
    locale: str | None = None
    timezone: str | None = None

    model_config = {"extra": "forbid"}
