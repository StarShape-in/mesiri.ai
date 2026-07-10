"""Interaction layer (M7) — human-in-the-loop confirm/reject/cancel of a workflow.

Owns message interpretation (is this a reply to the pending workflow?) and the
explicit RESUME-vs-NEW_JOURNEY decision. Delegates the actual workflow state
transition to the Workflow Runtime (it owns workflow_instances). May import
workflows/ (per the arch dependency chain); workflows/ never imports this.
"""

from __future__ import annotations

from .builder import build_interaction_handler
from .classifier import classify_reply
from .confirmation import format_confirmation_message
from .handler import InteractionHandled, InteractionHandler
from .intent import InteractionIntent
from .policy import InteractionDecision, InteractionRoute, decide
from .response_handler import render_resume_reply, render_workflow_run_reply

__all__ = [
    "InteractionIntent",
    "classify_reply",
    "InteractionDecision",
    "InteractionRoute",
    "decide",
    "InteractionHandler",
    "InteractionHandled",
    "build_interaction_handler",
    "format_confirmation_message",
    "render_resume_reply",
    "render_workflow_run_reply",
]
