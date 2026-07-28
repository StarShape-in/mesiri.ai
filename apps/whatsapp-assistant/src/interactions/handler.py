"""InteractionHandler — the fork between resuming a workflow and a new journey.

Sits after the identity gate and before the understanding pipeline. If the user
has an AWAITING_CONFIRMATION workflow and the reply is a confirmation
intent, the fast path resumes the workflow and returns the reply — the AI
pipeline is never touched (a plain "yes" costs no tokens). Otherwise the fast
path returns None and the caller runs the normal understanding journey, which
gives the slow path (LLM-classified, multi-segment) a chance to resolve
corrections or a confirmation the heuristic classifier missed.

When a CONFIRM resolves to WorkflowResumeStatus.CONFIRMED and a dispatcher is
wired (M8), the confirmed action is executed synchronously in the same
request and the reply reflects the real domain outcome (SUCCEEDED/REJECTED/
FAILED) rather than optimistically assuming the domain write happened. This
applies on both paths — a confirm resolved via the slow path must not skip
domain execution, or its reply would repeat the exact "recorded" bug M8 was
built to fix.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from dataclasses import dataclass, field
from typing import Any

from backend.ports import ActorIdentity
from channel.replies import (
    CATEGORY_ROWS,
    IMAGE_PURPOSE_ROWS,
    IMAGE_PURPOSE_SEMANTIC_HINT,
    ReplySpec,
    render_category_prompt,
    render_completion_photo_followup,
    render_greeting_menu,
    render_material_direction_followup,
)
from context.live_identity import whoami_reply
from memory.coordinator import ConversationMemoryCoordinator
from mesiri_ai.greeting_classifier import is_greeting_trigger
from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from mesiri_contracts.assistant.v2.interaction_spec import InteractionIntent
from planner import Planner
from workflows import WorkflowResumeResult, WorkflowResumeStatus, WorkflowRunResult, WorkflowRuntime
from workflows.batch import (
    format_batch_summary,
    format_started_segment_reply,
    start_segment,
    summarize_batch_outcome,
)
from workflows.batch_store import PendingBatchStore
from workflows.who_am_i import is_whoami_trigger

from .classifier import classify_reply
from .classifier_port import InteractionClassifierPort
from .completion_photo_hint import CompletionPhotoHintStore
from .policy import InteractionRoute, decide
from .ports import ExecutionDispatcher, ReceiptBuilder
from .response_handler import render_execution_reply, render_resume_reply, render_workflow_run_reply

logger = logging.getLogger(__name__)

#: Interactive reply ids owned by the app's own fixed pickers, which
#: handle_slot_answer must never consume as an answer to a workflow's slot
#: question. Derived from the row definitions rather than written out, so a
#: new row cannot be added to a picker without also being protected here.
_FOREIGN_PICKER_IDS: frozenset[str] = frozenset(
    row.id for row in (*IMAGE_PURPOSE_ROWS, *CATEGORY_ROWS)
)


@dataclass(slots=True)
class InteractionHandled:
    """Returned when the message was handled as a workflow interaction."""

    result: WorkflowResumeResult | WorkflowRunResult
    reply_text: str
    execution_result: ExecutionResult | None = None
    unrelated_text: str | None = None
    # Post-confirmation receipt image (see channel/receipt/). None for every
    # outcome except a successful execution -- and even then, only when
    # rendering actually produced bytes (ReceiptBuilder degrades to None on
    # any failure rather than raising).
    #
    # Phase 4: this field carries the pre-built bytes only when the caller
    # has already awaited receipt_coro. Prefer receipt_coro for new call sites
    # so text can be sent first without waiting for the Playwright render.
    reply_image: bytes | None = None
    # Coroutine that produces the receipt PNG (or None on failure). Awaiting
    # this after sending reply_text lets the user see the confirmation text
    # immediately while the image renders in the background.
    receipt_coro: Coroutine[Any, Any, bytes | None] | None = field(default=None, repr=False)
    project_id: str | None = None
    site_id: str | None = None


class InteractionHandler:
    def __init__(
        self,
        workflow_runtime: WorkflowRuntime,
        classifier: InteractionClassifierPort | None = None,
        dispatcher: ExecutionDispatcher | None = None,
        receipt_builder: ReceiptBuilder | None = None,
        memory_coordinator: ConversationMemoryCoordinator | None = None,
        planner: Planner | None = None,
        batch_store: PendingBatchStore | None = None,
        completion_photo_hint_store: CompletionPhotoHintStore | None = None,
    ) -> None:
        self._runtime = workflow_runtime
        self._classifier = classifier
        self._dispatcher = dispatcher
        self._receipt_builder = receipt_builder
        self._memory_coordinator = memory_coordinator
        self._planner = planner
        self._batch_store = batch_store
        self._completion_photo_hint_store = completion_photo_hint_store

    async def _resume_and_render(
        self, user_id: str, loaded, resume_action, *, log_prefix: str, actor: ActorIdentity | None = None
    ) -> tuple[WorkflowResumeResult, str, ExecutionResult | None, Coroutine[Any, Any, bytes | None] | None]:
        """Resume the workflow and, if it lands on CONFIRMED and a dispatcher is
        wired (M8), execute the domain write synchronously and reflect the real
        outcome in the reply. Shared by the fast and slow paths so a confirm
        resolved either way gets the same execution guarantee.

        Phase 4: the receipt PNG is no longer awaited here. The coroutine to
        produce it is returned as the 4th element so callers can send
        ``reply_text`` immediately and render the image afterwards.
        """
        result = await self._runtime.resume(loaded, resume_action)
        logger.info(
            "%s.resumed user=%s status=%s instance=%s",
            log_prefix,
            user_id,
            result.status.value,
            result.workflow_instance_id,
        )

        execution_result: ExecutionResult | None = None
        receipt_coro: Coroutine[Any, Any, bytes | None] | None = None
        if result.status is WorkflowResumeStatus.CONFIRMED and self._dispatcher is not None:
            assert result.confirmed_action is not None
            execution_result = await self._dispatcher.dispatch(result.confirmed_action)
            logger.info(
                "%s.executed user=%s status=%s instance=%s",
                log_prefix,
                user_id,
                execution_result.status.value,
                result.workflow_instance_id,
            )
            reply_text = render_execution_reply(execution_result)
            # Both the M19 memory hook and the #25 completion-photo follow-up
            # need "which activity did this touch" -- computed once here,
            # independent of either being wired, so neither accidentally
            # depends on the other being enabled (a real bug caught by
            # test_completion_photo_followup_trigger.py: this used to sit
            # inside the memory_coordinator-only branch, so the follow-up
            # silently never fired when memory_coordinator was None).
            activity_id: str | None = None
            if (
                execution_result.status is ExecutionStatus.SUCCEEDED
                and execution_result.material_row_id is not None
                and result.confirmed_action.draft_action.action_type
                in (DraftActionType.CREATE_ACTIVITY, DraftActionType.ADD_PROGRESS_UPDATE)
            ):
                # ADD_PROGRESS_UPDATE's execution result carries the
                # Activity's own id, not the new Progress Update's, since
                # the thing worth remembering/following-up on is the
                # activity, not the append-only row this one produced.
                activity_id = (
                    execution_result.material_row_id
                    if result.confirmed_action.draft_action.action_type
                    is DraftActionType.CREATE_ACTIVITY
                    else result.confirmed_action.draft_action.fields.get("activity_id")
                )

            if activity_id and self._memory_coordinator is not None:
                # M19: remember the activity THIS conversation just touched --
                # see memory/conversation_scope.py's CurrentActivityStore and
                # runtime/inbound_journey.py's _seed_open_activity, which
                # prefers this over the site-wide "most recently updated"
                # guess on the next continuation message. Fire-and-forget:
                # memory bookkeeping must never delay or fail a reply.
                asyncio.ensure_future(
                    self._memory_coordinator.record_activity(
                        user_id=user_id, activity_id=str(activity_id)
                    )
                )

            if (
                activity_id
                and self._completion_photo_hint_store is not None
                and result.confirmed_action.draft_action.action_type
                is DraftActionType.ADD_PROGRESS_UPDATE
                and str(
                    result.confirmed_action.draft_action.fields.get("update_kind") or ""
                ).upper()
                == "COMPLETED"
            ):
                # #25 AI Follow-up: an Activity just marked COMPLETED is
                # exactly the moment a completion photo is most useful and
                # least likely to be sent unprompted. The hint set here lets
                # the NEXT photo skip the normal "what is this for?" picker
                # entirely (see runtime/dependencies.py's image-arrival
                # block) -- the user is plainly answering the question
                # Mesiri just asked.
                asyncio.ensure_future(
                    self._completion_photo_hint_store.set_hint(
                        user_id=user_id, activity_id=str(activity_id)
                    )
                )
                reply_text = f"{reply_text}\n\n{render_completion_photo_followup()}"
            if self._receipt_builder is not None:
                # Return the coroutine without awaiting it — the caller sends
                # reply_text first so the user sees confirmation immediately,
                # then awaits this to get the image bytes.
                receipt_coro = self._receipt_builder.build(
                    result.confirmed_action, execution_result, actor
                )
        else:
            reply_text = render_resume_reply(result)

        # #1 Multi-Activity / #13 Cross-Module Trigger: this resolution may
        # be one segment of a multi-segment batch (runtime/inbound_journey.py
        # queued the rest after the first segment started -- see
        # workflows/batch_store.py). Record this segment's outcome and
        # either start the next queued one (appending ITS prompt to the same
        # reply) or, if this was the last, append the whole batch's summary.
        # A no-op for the overwhelming common case: has_pending is False for
        # every ordinary single-segment message.
        if self._batch_store is not None and self._planner is not None:
            has_batch = await self._batch_store.has_pending(user_id=user_id)
            if has_batch:
                await self._batch_store.record_outcome(
                    user_id=user_id,
                    outcome=summarize_batch_outcome(result, execution_result),
                )
                next_item = await self._batch_store.pop_next(user_id=user_id)
                if next_item is not None:
                    next_event, progress = next_item
                    next_run = await start_segment(
                        next_event, planner=self._planner, workflow_runtime=self._runtime
                    )
                    reply_text = f"{reply_text}\n\n{format_started_segment_reply(next_run, progress)}"
                else:
                    outcomes = await self._batch_store.get_outcomes(user_id=user_id)
                    reply_text = reply_text + format_batch_summary(outcomes)
                    await self._batch_store.clear(user_id=user_id)

        return result, reply_text, execution_result, receipt_coro

    async def handle_fast_path(
        self, user_id: str, message: NormalizedMessage, actor: ActorIdentity | None = None
    ) -> InteractionHandled | None:
        loaded = await self._runtime.get_awaiting_confirmation(user_id)
        if loaded is None:
            return None  # no pending workflow → normal journey

        intent = classify_reply(message.text)
        decision = decide(intent)
        if decision.route is InteractionRoute.NEW_JOURNEY:
            # A user with a pending confirmation can still send an unrelated
            # message — it must NOT be swallowed by the active workflow.
            logger.info(
                "interaction.new_journey user=%s intent=%s pending=%s",
                user_id,
                intent.value,
                loaded.state.workflow_instance_id,
            )
            return None

        result, reply_text, execution_result, receipt_coro = await self._resume_and_render(
            user_id, loaded, decision.resume_action, log_prefix="interaction", actor=actor
        )
        return InteractionHandled(
            result=result,
            reply_text=reply_text,
            execution_result=execution_result,
            receipt_coro=receipt_coro,
            project_id=str(loaded.state.project_id) if loaded.state.project_id else None,
            site_id=str(loaded.state.site_id) if loaded.state.site_id else None,
        )

    async def handle_slot_answer(
        self, user_id: str, message: NormalizedMessage
    ) -> InteractionHandled | None:
        """Fast path for a reply to an open COLLECTING_FIELDS slot question
        (Finance Module Slice 1 -- e.g. "which account?"). Text/interactive
        only, same reasoning as handle_whoami_trigger: voice has no text
        until Sarvam transcribes it, so this can't run pre-transcription. A
        slot question left unanswered by voice simply falls through to the
        normal journey, where WorkflowRuntime.start()'s single-active
        pre-check turns any new intent into a "finish this first" block
        rather than silently starting a second workflow.

        Deterministic list/number matching happens inside the workflow graph
        (see expense_capture/nodes.py's resolve_account) via
        WorkflowRuntime.provide_input() -- no AI call here, same "a plain
        reply costs no tokens" principle as handle_fast_path.
        """
        if message.modality not in (InputModality.TEXT, InputModality.INTERACTIVE):
            return None
        # A tap belonging to one of the app's own fixed pickers is never an
        # answer to a slot question. Slot options carry dynamic values --
        # worker ids, account ids -- never these literals, so an id from this
        # set means the user is answering something else entirely.
        #
        # This runs before both the category-tap handler and the image-purpose
        # picker (see runtime/dependencies.py's ordering), so without the
        # check it swallows their taps: with a promotion offer open, choosing
        # "Attendance" for a photo was consumed as a worker name and answered
        # "Sorry, I didn't catch that" -- and the photo was never processed.
        if message.modality is InputModality.INTERACTIVE:
            tapped = str((message.metadata or {}).get("interactive_reply_id") or "")
            if tapped in _FOREIGN_PICKER_IDS:
                return None
        loaded = await self._runtime.get_awaiting_input(user_id)
        if loaded is None:
            return None
        if not message.text:
            return None

        result = await self._runtime.provide_input(loaded, message.text)
        logger.info(
            "interaction.slot_answered user=%s status=%s instance=%s",
            user_id,
            result.status.value,
            result.workflow_instance_id,
        )
        reply_text = render_workflow_run_reply(result, pending_prompt=result.pending_prompt)
        return InteractionHandled(
            result=result,
            reply_text=reply_text,
            project_id=str(loaded.state.project_id) if loaded.state.project_id else None,
            site_id=str(loaded.state.site_id) if loaded.state.site_id else None,
        )

    def handle_category_tap(self, message: NormalizedMessage) -> ReplySpec | None:
        """A tap on the category-menu list (see channel/replies.CATEGORY_ROWS,
        sent by render_direct_reply's greeting). Deterministic -- we defined
        these row ids ourselves, so recognizing one needs no AI call, same
        principle as handle_fast_path ("a plain yes costs no tokens"). Never
        touches WorkflowRuntime: a category tap isn't resuming or starting a
        workflow, just picking which one to describe next.

        Synchronous and I/O-free, unlike handle_fast_path/handle_slow_path --
        there's nothing here to await.

        Returns None for anything that isn't a recognized menu tap (not an
        interactive reply at all, or a stale/foreign button id), so the
        caller falls through to the normal journey exactly like the other
        fast-path checks.
        """
        if message.modality is not InputModality.INTERACTIVE:
            return None
        row_id = message.metadata.get("interactive_reply_id")
        if not row_id:
            return None
        return render_category_prompt(row_id)

    def handle_material_direction_tap(self, message: NormalizedMessage) -> str | None:
        """A tap on the Material Arrived/Used buttons (see channel/replies.py
        MATERIAL_DIRECTION_BUTTONS, sent by render_category_prompt's
        "cat_material" case). Deterministic, same principle as
        handle_category_tap -- this only recognizes the two ids we defined
        ourselves and returns the tailored follow-up prompt text; the caller
        (runtime/dependencies.py) is responsible for locking the direction
        into category_hint_store so canonicalization can use it as a fallback
        default.

        Returns None for anything else, so the caller falls through to the
        normal journey exactly like the other fast-path checks.
        """
        if message.modality is not InputModality.INTERACTIVE:
            return None
        row_id = message.metadata.get("interactive_reply_id")
        if row_id == "dir_received":
            return render_material_direction_followup("received")
        if row_id == "dir_used":
            return render_material_direction_followup("used")
        return None

    def handle_image_purpose_tap(self, message: NormalizedMessage) -> str | None:
        """A tap on the "what is this photo for?" list (see
        channel/replies.IMAGE_PURPOSE_ROWS, sent when a genuinely new image
        arrives -- see runtime/dependencies.py). Deterministic, same
        principle as handle_category_tap. Returns the raw row_id (not yet
        the semantic hint) so the caller can special-case "img_site_update"
        (#2 Batch Media: a direct evidence attach via
        runtime/evidence_query.py, never a workflow -- see
        AttachEvidenceCommand's docstring) separately from "img_expense"
        (re-processes the held image via IMAGE_PURPOSE_SEMANTIC_HINT).

        Returns None for anything that isn't a recognized menu tap, so the
        caller falls through to the normal journey exactly like the other
        fast-path checks.
        """
        if message.modality is not InputModality.INTERACTIVE:
            return None
        row_id = message.metadata.get("interactive_reply_id")
        if row_id not in IMAGE_PURPOSE_SEMANTIC_HINT:
            return None
        return row_id

    def handle_greeting_trigger(
        self, message: NormalizedMessage, *, timezone: str | None = None
    ) -> ReplySpec | None:
        """A bare "hi"/"menu"/"help"/etc, matched against a deterministic,
        configurable phrase list (greeting_phrases.json) -- never the AI
        pipeline's judgment call. "hi" must reliably open the menu regardless
        of what an extraction provider would have classified it as.

        Text-only: for TEXT/INTERACTIVE modality, message.text is already
        populated at normalization time, so this runs before Understanding
        is even invoked -- the biggest saving (translation + extraction both
        skipped), same principle as handle_fast_path. Voice can't be checked
        here: there's no text until Sarvam transcribes it. The identical
        phrase check runs again post-transcription, pre-extraction, inside
        understanding/pipeline.py's _handle_voice -- deterministic either
        way, just a smaller saving for voice (STT is unavoidable).

        `is_first_message` isn't threaded through here (not wired anywhere
        yet, see channel/replies.py) -- always renders the returning-user
        copy. timezone is best-effort: at this point in the journey (before
        M4 Context resolution) the caller only has the cheaper identity gate,
        which doesn't carry a timezone, so this is usually None and falls
        back to a neutral "Hello" (see channel/replies._greeting).
        """
        if message.modality is not InputModality.TEXT:
            return None
        if not is_greeting_trigger(message.text):
            return None
        return render_greeting_menu(timezone=timezone)

    def handle_whoami_trigger(self, message: NormalizedMessage, actor: ActorIdentity) -> str | None:
        """A bare "who am i"/"whoami"/"my profile"/etc (see
        workflows.who_am_i.phrases.json) -- deterministic identity-lookup fast
        path, no AI call, same principle as handle_greeting_trigger ("a plain
        question costs no tokens"). Unlike the greeting trigger this needs the
        caller's already-resolved ActorIdentity (name/role/org/projects/sites)
        to build the reply, hence the extra parameter -- the caller (M4's
        identity gate, in runtime/dependencies.py) already has it before this
        runs, so there's no extra lookup.

        Text-only, same reasoning as handle_greeting_trigger: voice has no
        text until Sarvam transcribes it, and this isn't wired into the
        post-transcription path (understanding/pipeline.py has no identity to
        build the reply from).
        """
        if message.modality is not InputModality.TEXT:
            return None
        if not is_whoami_trigger(message.text):
            return None
        return whoami_reply(actor)

    async def handle_slow_path(
        self,
        user_id: str,
        message: NormalizedMessage,
        original_text: str,
        translated_text: str | None,
        actor: ActorIdentity | None = None,
    ) -> InteractionHandled | None:
        if self._classifier is None:
            return None

        loaded = await self._runtime.get_awaiting_confirmation(user_id)
        if loaded is None:
            return None

        try:
            spec = await self._classifier.classify(
                original_text,
                translated_text,
                loaded.state.draft_action.fields,
                message.correlation_id,
            )
        except Exception:
            logger.exception(
                "interaction.slow_path.classifier_failed correlation_id=%s", message.correlation_id
            )
            # Create a dummy spec with AMBIGUOUS intent to trigger fallback
            from mesiri_contracts.assistant.v2.interaction_spec import (
                InteractionSegment,
                InteractionSpecV2,
            )

            spec = InteractionSpecV2(
                correlation_id=message.correlation_id,
                segments=[
                    InteractionSegment(
                        intent=InteractionIntent.AMBIGUOUS, segment_text=original_text
                    )
                ],
            )

        unrelated_segments: list[str] = []
        handled_result: WorkflowRunResult | WorkflowResumeResult | None = None
        execution_result: ExecutionResult | None = None
        reply_text: str | None = None
        receipt_coro: Coroutine[Any, Any, bytes | None] | None = None

        for segment in spec.segments:
            if segment.intent == InteractionIntent.UNRELATED:
                unrelated_segments.append(segment.segment_text)
                continue

            if segment.intent == InteractionIntent.AMBIGUOUS:
                # Explicit fallback: prompt the user to re-state their correction cleanly
                if handled_result is None:
                    handled_result = WorkflowRunResult.failed(
                        workflow_key=loaded.state.workflow_key,
                        correlation_id=message.correlation_id,
                    )
                    reply_text = "I heard you wanted to make a change, but I couldn't quite catch the specific details. Could you repeat just the part you want to correct?"
                continue

            if segment.intent == InteractionIntent.CORRECTION:
                if handled_result is None:
                    run_result = await self._runtime.correct(loaded, segment.corrections)
                    logger.info(
                        "interaction.slow_path.corrected user=%s instance=%s",
                        user_id,
                        loaded.state.workflow_instance_id,
                    )
                    handled_result = run_result
                    reply_text = render_workflow_run_reply(
                        run_result, pending_prompt=run_result.pending_prompt
                    )
                continue

            # CONFIRM, REJECT, CANCEL
            decision = decide(segment.intent)
            if decision.route is InteractionRoute.NEW_JOURNEY:
                # E.g. decide(AMBIGUOUS) -> NEW_JOURNEY, but we handled AMBIGUOUS above.
                # If something else triggers NEW_JOURNEY, treat it as unrelated.
                unrelated_segments.append(segment.segment_text)
                continue

            if handled_result is None:
                result, reply_text, execution_result, receipt_coro = await self._resume_and_render(
                    user_id,
                    loaded,
                    decision.resume_action,
                    log_prefix="interaction.slow_path",
                    actor=actor,
                )
                handled_result = result
            continue

        unrelated_text = " ".join(unrelated_segments) if unrelated_segments else None

        if handled_result is not None and reply_text is not None:
            return InteractionHandled(
                result=handled_result,
                reply_text=reply_text,
                execution_result=execution_result,
                unrelated_text=unrelated_text,
                receipt_coro=receipt_coro,
                project_id=str(loaded.state.project_id) if loaded.state.project_id else None,
                site_id=str(loaded.state.site_id) if loaded.state.site_id else None,
            )

        # If nothing triggered a workflow change (e.g. only UNRELATED segments),
        # return None to let inbound_journey run the whole thing as a new journey.
        if unrelated_segments:
            logger.info(
                "interaction.slow_path.only_unrelated user=%s instance=%s",
                user_id,
                loaded.state.workflow_instance_id,
            )
        return None
