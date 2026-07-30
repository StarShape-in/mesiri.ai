"""Resumes the whole-plan preview's Yes/No tap
(docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §8, P3).

try_start_decomposed_plan (decomposed_plan.py) persists a Plan with every
step PENDING and sends the preview -- nothing has started yet. This module
is the other half: the sender's answer to that preview.

Mirrors resume_pending_report_with_member_create_offer's row-id-tap shape
exactly (a bare INTERACTIVE tap, no pending_report to pop, dispatched from
message_journey.py's same row-id chain).
"""

from __future__ import annotations

from channel.replies import (
    PLAN_CONFIRM_NO_ROW_ID,
    PLAN_CONFIRM_YES_ROW_ID,
    ReplySpec,
    render_plan_cancelled_reply,
    render_plan_confirmation_expired_reply,
)
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from planning.plan_store import PlanStore
from runtime.inbound_journey._shared import _log
from runtime.inbound_journey.reply import _safe
from runtime.logging_ports import MessageLogger
from runtime.plan_executor import begin_plan
from workflows import WorkflowRuntime


async def resume_pending_plan_confirmation(
    message: NormalizedMessage,
    actor_user_id: str,
    *,
    plan_store: PlanStore,
    workflow_runtime: WorkflowRuntime,
    message_logger: MessageLogger | None = None,
) -> ReplySpec | None:
    """A tap on the whole-plan preview's Yes/No. Yes begins execution (the
    first step's own confirmation prompt, or -- in the rare case every step
    resolves without asking anything -- the closing summary); No discards
    the plan entirely. Returns None for anything that isn't one of these two
    row ids, so the caller falls through to the normal journey exactly like
    every other fast-path check.
    """
    if message.modality is not InputModality.INTERACTIVE:
        return None
    row_id = message.metadata.get("interactive_reply_id")
    if row_id not in (PLAN_CONFIRM_YES_ROW_ID, PLAN_CONFIRM_NO_ROW_ID):
        return None

    if row_id == PLAN_CONFIRM_NO_ROW_ID:
        # No pop-and-check first: clearing an already-empty/expired plan is a
        # harmless no-op (PlanStore.clear just overwrites with an
        # immediately-expired marker), and the reply reads the same either
        # way -- there is nothing left to discard that the user would need
        # told apart from "already gone".
        await _safe(plan_store.clear(user_id=actor_user_id))
        if message_logger is not None:
            await _safe(message_logger.mark_completed(correlation_id=message.correlation_id))
        return ReplySpec(text=render_plan_cancelled_reply())

    plan = await plan_store.get_plan(user_id=actor_user_id)
    if plan is None:
        if message_logger is not None:
            await _safe(message_logger.mark_completed(correlation_id=message.correlation_id))
        return ReplySpec(text=render_plan_confirmation_expired_reply())

    try:
        reply = await begin_plan(
            user_id=actor_user_id, plan_store=plan_store, workflow_runtime=workflow_runtime
        )
    except Exception:  # noqa: BLE001 -- a tap must always get some reply, and the
        # plan is left in place rather than guessed at -- a retry (re-tapping
        # Yes) is safe, since begin_plan only ever starts whatever is still
        # PENDING.
        _log.exception("plan.begin_failed user=%s", actor_user_id)
        if message_logger is not None:
            await _safe(message_logger.mark_completed(correlation_id=message.correlation_id))
        return ReplySpec(text="Sorry, I couldn't start that — please try again.")

    if message_logger is not None:
        await _safe(message_logger.mark_completed(correlation_id=message.correlation_id))
    if reply is None:
        # begin_plan found nothing runnable and nothing to summarize -- an
        # empty plan should never reach here (build_plan_from_segments
        # returns None rather than a zero-step Plan), so this is defensive
        # rather than an expected outcome.
        return ReplySpec(text=render_plan_confirmation_expired_reply())
    return reply
