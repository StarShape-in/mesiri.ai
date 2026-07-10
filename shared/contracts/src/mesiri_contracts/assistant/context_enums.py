"""Context enumerations for ResolvedContext.v1 (M4).

``ContextSource`` records *why* a project/site was selected — the precedence
tier that won. ``ContextConfidence`` is a coarse, ordered classification derived
*deterministically* from resolution evidence (never asked of an LLM).

Ownership: SHARED ARCHITECTURE — part of the M0 contract surface.
"""

from __future__ import annotations

from enum import Enum


class ContextSource(str, Enum):
    """The precedence tier that supplied the resolved project/site.

    Ordered most-authoritative-first; the precedence policy evaluates candidates
    in this order (see M4 precedence policy).
    """

    MESSAGE_EXPLICIT = "message_explicit"  # named/identified in the current message
    REPLY_CONTEXT = "reply_context"  # inherited from a WhatsApp reply target
    WORKFLOW_CONTEXT = "workflow_context"  # supplied by an active workflow (via port)
    ACTIVE_CONTEXT = "active_context"  # user's ephemeral active context (Redis)
    USER_DEFAULT = "user_default"  # user's default assignment (Postgres)
    USER_SELECTED = "user_selected"  # explicit prior selection (context switch)
    UNRESOLVED = "unresolved"  # no candidate resolved


class ContextConfidence(str, Enum):
    """How confident the resolver is in the selected project/site."""

    VERY_HIGH = "very_high"  # explicit, unique, authorized id match
    HIGH = "high"  # explicit unique name / validated reply / workflow
    MEDIUM = "medium"  # active or default assignment
    LOW = "low"  # weak / partial evidence
    AMBIGUOUS = "ambiguous"  # multiple authorized candidates matched
    UNRESOLVED = "unresolved"  # no candidate resolved

    @property
    def rank(self) -> int:
        return {
            "unresolved": 0,
            "ambiguous": 1,
            "low": 2,
            "medium": 3,
            "high": 4,
            "very_high": 5,
        }[self.value]
