"""Interaction layer (M7) — human-in-the-loop confirm/reject/cancel of a workflow.

Owns message interpretation (is this a reply to the pending workflow?) and the
explicit RESUME-vs-NEW_JOURNEY decision. Delegates the actual workflow state
transition to the Workflow Runtime (it owns workflow_instances). May import
workflows/ (per the arch dependency chain); workflows/ never imports this.
"""

from __future__ import annotations

from .classifier import classify_reply
from .handler import InteractionHandled, InteractionHandler
from .intent import InteractionIntent
from .policy import InteractionDecision, InteractionRoute, decide

__all__ = [
    "InteractionIntent",
    "classify_reply",
    "InteractionDecision",
    "InteractionRoute",
    "decide",
    "InteractionHandler",
    "InteractionHandled",
]
