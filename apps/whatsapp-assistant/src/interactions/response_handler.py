"""Interaction reply rendering — single source of truth for interaction-leg replies.

All text the assistant sends back to the user as a result of an interaction
(resume, blocked, ambiguous) is defined here. No business logic — purely
string rendering. Localisation / WhatsApp template migration happens here, not
in the callers.
"""

from __future__ import annotations
from workflows import WorkflowResumeResult, WorkflowResumeStatus, WorkflowRunResult, WorkflowRunStatus


def render_resume_reply(result: WorkflowResumeResult) -> str:
    """Human-readable reply after a workflow interaction (confirm / reject / cancel).

    Localisation and rich WhatsApp templates are future work; string constants
    live here so the migration touches exactly one file.
    """
    if result.status is WorkflowResumeStatus.CONFIRMED:
        return "✅ Recorded. Thank you."
    if result.status is WorkflowResumeStatus.REJECTED:
        return "❌ Discarded. Nothing was recorded."
    if result.status is WorkflowResumeStatus.CANCELLED:
        return "Cancelled. Nothing was recorded."
    # ALREADY_RESOLVED (duplicate delivery / double reply) or NOT_RESUMABLE.
    return "That request was already handled."


def render_workflow_run_reply(result: WorkflowRunResult, *, pending_prompt: str) -> str:
    """Reply to send after a workflow *starts* (STARTED or BLOCKED_PENDING_CONFIRMATION).

    ``pending_prompt`` is the text produced by the workflow graph — passed in
    rather than read from ``result`` so the caller controls which prompt is used
    (e.g. the *existing* workflow's prompt when blocked).
    """
    if result.status is WorkflowRunStatus.BLOCKED_PENDING_CONFIRMATION:
        return f"⏳ Please finish the pending confirmation first:\n\n{pending_prompt}"
    # STARTED — show the workflow's confirmation request directly.
    return pending_prompt
