"""Interaction reply rendering — single source of truth for interaction-leg replies.

All text the assistant sends back to the user as a result of an interaction
(resume, blocked, ambiguous) is defined here. No business logic — purely
string rendering. Localisation / WhatsApp template migration happens here, not
in the callers.
"""

from __future__ import annotations

from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from workflows import (
    WorkflowResumeResult,
    WorkflowResumeStatus,
    WorkflowRunResult,
    WorkflowRunStatus,
)


def render_resume_reply(result: WorkflowResumeResult) -> str:
    """Human-readable reply after a workflow interaction (confirm / reject / cancel).

    Localisation and rich WhatsApp templates are future work; string constants
    live here so the migration touches exactly one file.

    Note: the CONFIRMED branch here is only reached when no ExecutionDispatcher
    is wired (e.g. M7-only tests). When M8 execution runs, CONFIRMED replies go
    through render_execution_reply() instead, which reflects the real domain
    outcome rather than optimistically assuming a domain write happened.
    """
    if result.status is WorkflowResumeStatus.CONFIRMED:
        return "✅ Recorded. Thank you."
    if result.status is WorkflowResumeStatus.REJECTED:
        return "❌ Discarded. Nothing was recorded."
    if result.status is WorkflowResumeStatus.CANCELLED:
        return "Cancelled. Nothing was recorded."
    # ALREADY_RESOLVED (duplicate delivery / double reply) or NOT_RESUMABLE.
    return "That request was already handled."


def render_execution_reply(result: ExecutionResult) -> str:
    """Reply after M8 execution actually runs — reflects the real domain outcome,
    not just "the user confirmed" (fixes the M7 always-optimistic reply bug)."""
    if result.status in (ExecutionStatus.SUCCEEDED, ExecutionStatus.ALREADY_EXECUTED):
        return "✅ Recorded. Thank you."
    if result.status is ExecutionStatus.REJECTED:
        reasons = "; ".join(result.rejection_reasons)
        return f"⚠️ Couldn't record this: {reasons}"
    # FAILED
    return "⚠️ Something went wrong — we'll retry automatically."


def render_workflow_run_reply(result: WorkflowRunResult, *, pending_prompt: str | None = None) -> str:
    """Reply to send after a workflow run.

    ``pending_prompt`` is the text produced by the workflow graph — passed in
    rather than read from ``result`` so the caller controls which prompt is used
    (e.g. the *existing* workflow's prompt when blocked).
    """
    if result.status is WorkflowRunStatus.FAILED:
        return "Sorry, I couldn't apply that update — please try again."
    if result.status is WorkflowRunStatus.BLOCKED_PENDING_CONFIRMATION:
        return f"⏳ Please finish the pending confirmation first:\n\n{pending_prompt}"
    # STARTED — show the workflow's confirmation request directly.
    return pending_prompt or ""
