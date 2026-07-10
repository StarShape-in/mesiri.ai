"""Deterministic context precedence + confidence policy (M4).

Precedence (most authoritative first):

    1. MESSAGE_EXPLICIT  — a project/site named or identified in *this* message
    2. REPLY_CONTEXT     — inherited from a WhatsApp reply target
    3. WORKFLOW_CONTEXT  — supplied by an active workflow (via port; M5 owns it)
    4. ACTIVE_CONTEXT    — the user's ephemeral active context (Redis)
    5. USER_DEFAULT      — the user's default assignment (Postgres)
    6. UNRESOLVED        — nothing resolved

Only *authorized* candidates are ever selected. Confidence is derived purely
from resolution evidence — never asked of an LLM.
"""

from __future__ import annotations

from mesiri_contracts.assistant.context_enums import ContextConfidence, ContextSource

from .models import ContextCandidate

# Lower number == higher precedence.
_PRECEDENCE: dict[ContextSource, int] = {
    ContextSource.MESSAGE_EXPLICIT: 1,
    ContextSource.REPLY_CONTEXT: 2,
    ContextSource.WORKFLOW_CONTEXT: 3,
    ContextSource.ACTIVE_CONTEXT: 4,
    ContextSource.USER_SELECTED: 4,
    ContextSource.USER_DEFAULT: 5,
    ContextSource.UNRESOLVED: 99,
}


def precedence_rank(source: ContextSource) -> int:
    return _PRECEDENCE.get(source, 99)


def select(candidates: list[ContextCandidate]) -> ContextCandidate | None:
    """Return the highest-precedence *authorized* candidate, or None.

    Deterministic: ties break by ``(precedence, source value, project_id,
    site_id)`` so the same inputs always yield the same winner.
    """
    authorized = [c for c in candidates if c.authorized]
    if not authorized:
        return None
    return min(
        authorized,
        key=lambda c: (
            precedence_rank(c.source),
            c.source.value,
            c.project_id or "",
            c.site_id or "",
        ),
    )


# -- Confidence derivation ---------------------------------------------------


def confidence_for_explicit(*, by_id: bool) -> ContextConfidence:
    """Explicit reference in the current message."""
    return ContextConfidence.VERY_HIGH if by_id else ContextConfidence.HIGH


def confidence_for_source(source: ContextSource) -> ContextConfidence:
    """Confidence for non-explicit candidate sources."""
    return {
        ContextSource.REPLY_CONTEXT: ContextConfidence.HIGH,
        ContextSource.WORKFLOW_CONTEXT: ContextConfidence.HIGH,
        ContextSource.ACTIVE_CONTEXT: ContextConfidence.MEDIUM,
        ContextSource.USER_SELECTED: ContextConfidence.HIGH,
        ContextSource.USER_DEFAULT: ContextConfidence.MEDIUM,
    }.get(source, ContextConfidence.UNRESOLVED)
