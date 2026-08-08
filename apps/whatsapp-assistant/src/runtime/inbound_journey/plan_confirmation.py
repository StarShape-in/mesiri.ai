"""Resumes the whole-plan preview's Yes/No/Edit tap
(docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §8, P3, §12).

try_start_decomposed_plan (decomposed_plan.py) persists a Plan with every
step PENDING and sends the preview -- nothing has started yet. This module
is the other half: the sender's answer to that preview.

EDIT resolves §12's open question: "drop a step, or re-state the whole
request?" -- drop. Tapping Edit shows a picker of the plan's own steps;
tapping one removes it (and, per PlanStore.remove_step, every step that
depends on it) and re-shows the preview with whatever remains. There is no
free-text edit and no partial-field edit -- only "this step, or nothing
about it," which is the smallest thing that actually closes the gap between
"reject everything and resend" and "wrong plan, no way out short of that".

Mirrors resume_pending_report_with_member_create_offer's row-id-tap shape
exactly (a bare INTERACTIVE tap, no pending_report to pop, dispatched from
message_journey.py's same row-id chain).
"""

from __future__ import annotations

from channel.replies import (
    PLAN_CONFIRM_NO_ROW_ID,
    PLAN_CONFIRM_YES_ROW_ID,
    PLAN_EDIT_CANCEL_ROW_ID,
    PLAN_EDIT_ROW_ID,
    PLAN_REMOVE_ROW_PREFIX,
    ReplySpec,
    render_plan_cancelled_reply,
    render_plan_confirmation_expired_reply,
    render_plan_edit_picker,
    render_plan_emptied_by_edit_reply,
    render_plan_preview_reply,
)
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from planning.plan import Plan
from planning.plan_store import PlanStore
from planning.preview import describe_step, render_plan_preview
from runtime.inbound_journey._shared import _log
from runtime.inbound_journey.reply import _safe
from runtime.logging_ports import MessageLogger
from runtime.plan_executor import begin_plan
from workflows import WorkflowRuntime


def _preview_reply(plan: Plan) -> ReplySpec:
    return render_plan_preview_reply(render_plan_preview(plan))


def _edit_picker_reply(plan: Plan) -> ReplySpec:
    return render_plan_edit_picker(
        [(f"{PLAN_REMOVE_ROW_PREFIX}{step.step_id}", describe_step(step, plan)) for step in plan.steps]
    )


async def resume_pending_plan_confirmation(
    message: NormalizedMessage,
    actor_user_id: str,
    *,
    plan_store: PlanStore,
    workflow_runtime: WorkflowRuntime,
    message_logger: MessageLogger | None = None,
) -> ReplySpec | None:
    """A tap on the whole-plan preview, or on the step picker Edit opens.

    Yes begins execution (the first step's own confirmation prompt, or --
    in the rare case every step resolves without asking anything -- the
    closing summary). No discards the plan entirely. Edit shows a picker of
    the plan's current steps; tapping one removes it (and its dependents)
    and re-shows the preview; "Keep all" backs out unchanged. Returns None
    for anything that isn't one of these row ids, so the caller falls
    through to the normal journey exactly like every other fast-path check.
    """
    if message.modality is not InputModality.INTERACTIVE:
        return None
    row_id = str(message.metadata.get("interactive_reply_id") or "")
    is_removal_tap = row_id.startswith(PLAN_REMOVE_ROW_PREFIX)
    if row_id not in (
        PLAN_CONFIRM_YES_ROW_ID,
        PLAN_CONFIRM_NO_ROW_ID,
        PLAN_EDIT_ROW_ID,
        PLAN_EDIT_CANCEL_ROW_ID,
    ) and not is_removal_tap:
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

    if row_id in (PLAN_EDIT_ROW_ID, PLAN_EDIT_CANCEL_ROW_ID) or is_removal_tap:
        if message_logger is not None:
            await _safe(message_logger.mark_completed(correlation_id=message.correlation_id))

        if row_id == PLAN_EDIT_ROW_ID:
            plan = await plan_store.get_plan(user_id=actor_user_id)
            if plan is None:
                return ReplySpec(text=render_plan_confirmation_expired_reply())
            return _edit_picker_reply(plan)

        if row_id == PLAN_EDIT_CANCEL_ROW_ID:
            plan = await plan_store.get_plan(user_id=actor_user_id)
            if plan is None:
                return ReplySpec(text=render_plan_confirmation_expired_reply())
            return _preview_reply(plan)

        # A removal tap -- row_id is "plan_remove_<step_id>".
        step_id = row_id.removeprefix(PLAN_REMOVE_ROW_PREFIX)
        try:
            plan = await plan_store.remove_step(user_id=actor_user_id, step_id=step_id)
        except Exception:  # noqa: BLE001 -- an expired plan, a stale/replayed tap
            # naming a step_id from a plan that no longer exists, or one
            # already edited into a different shape -- never a crash, and
            # never silently mistaken for success.
            _log.warning(
                "plan.remove_step_failed user=%s step_id=%s", actor_user_id, step_id, exc_info=True
            )
            return ReplySpec(text=render_plan_confirmation_expired_reply())
        if plan is None:
            return ReplySpec(text=render_plan_emptied_by_edit_reply())
        return _preview_reply(plan)

    # row_id == PLAN_CONFIRM_YES_ROW_ID from here.
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
