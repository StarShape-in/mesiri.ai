"""Internal M4 domain models.

These are *resolution-internal* structures — authoritative rows read from
PostgreSQL and the ``ContextCandidate`` hypotheses the resolver ranks. They are
not part of the shared contract surface (only :class:`ResolvedContext` is). Kept
as frozen dataclasses so resolution stays side-effect free and easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mesiri_contracts.assistant.context_enums import ContextConfidence, ContextSource


@dataclass(frozen=True, slots=True)
class ExternalIdentity:
    """A channel identity (e.g. WhatsApp wa_id) mapped to an internal user."""

    provider: str
    external_subject: str
    user_id: str


@dataclass(frozen=True, slots=True)
class User:
    user_id: str
    is_active: bool = True
    locale: str | None = None
    timezone: str | None = None


@dataclass(frozen=True, slots=True)
class Organization:
    organization_id: str
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class Membership:
    membership_id: str
    organization_id: str
    user_id: str
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class Project:
    project_id: str
    organization_id: str
    name: str
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class Site:
    site_id: str
    project_id: str
    organization_id: str
    name: str
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class ContextPreferences:
    """A user's per-organization default assignment + locale/timezone."""

    organization_id: str
    user_id: str
    default_project_id: str | None = None
    default_site_id: str | None = None
    locale: str | None = None
    timezone: str | None = None


@dataclass(frozen=True, slots=True)
class ActiveContext:
    """Ephemeral active context read from Redis (never authoritative alone)."""

    organization_id: str
    user_id: str
    project_id: str | None
    site_id: str | None
    selected_at: str
    expires_at: str
    context_version: int = 1


@dataclass(frozen=True, slots=True)
class ContextCandidate:
    """One hypothesis for the message's project/site and why we believe it.

    ``authorized`` is filled by the authorization stage; the precedence policy
    only ever selects an authorized candidate. ``confidence`` is derived
    deterministically from ``source`` + match strength — never from an LLM.
    """

    source: ContextSource
    organization_id: str
    project_id: str | None = None
    site_id: str | None = None
    confidence: ContextConfidence = ContextConfidence.UNRESOLVED
    authorized: bool = False
    evidence: str | None = None
    # Reference text (e.g. a project name) that produced this candidate, if any.
    reference: str | None = None


@dataclass(slots=True)
class ResolutionTrace:
    """Accumulated resolution metadata (internal; drives observability/tests)."""

    candidates: list[ContextCandidate] = field(default_factory=list)
    events: list[tuple[str, dict]] = field(default_factory=list)
