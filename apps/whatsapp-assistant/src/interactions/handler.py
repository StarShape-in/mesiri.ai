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

import logging
from dataclasses import dataclass

from backend.ports import ActorIdentity
from channel.replies import ReplySpec, render_category_prompt, render_greeting_menu
from context.live_identity import whoami_reply
from mesiri_ai.greeting_classifier import is_greeting_trigger
from mesiri_contracts.application.results.execution_result import ExecutionResult
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from mesiri_contracts.assistant.v2.interaction_spec import InteractionIntent
from workflows import WorkflowResumeResult, WorkflowResumeStatus, WorkflowRunResult, WorkflowRuntime
from workflows.who_am_i import is_whoami_trigger

from .classifier import classify_reply
from .classifier_port import InteractionClassifierPort
from .policy import InteractionRoute, decide
from .ports import ExecutionDispatcher, ReceiptBuilder
from .response_handler import render_execution_reply, render_resume_reply, render_workflow_run_reply

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class InteractionHandled:
    """Returned when the message was handled as a workflow interaction."""

    result: WorkflowResumeResult | WorkflowRunResult
    reply_text: str
    execution_result: ExecutionResult | None = None
    unrelated_text: str | None = None
    # The post-confirmation receipt image (see channel/receipt/). None for
    # every outcome except a successful execution -- and even then, only
    # when rendering actually produced bytes (ReceiptBuilder degrades to
    # None on any failure rather than raising).
    reply_image: bytes | None = None
    project_id: str | None = None
    site_id: str | None = None


class InteractionHandler:
    def __init__(
        self,
        workflow_runtime: WorkflowRuntime,
        classifier: InteractionClassifierPort | None = None,
        dispatcher: ExecutionDispatcher | None = None,
        receipt_builder: ReceiptBuilder | None = None,
    ) -> None:
        self._runtime = workflow_runtime
        self._classifier = classifier
        self._dispatcher = dispatcher
        self._receipt_builder = receipt_builder

    async def _resume_and_render(
        self, user_id: str, loaded, resume_action, *, log_prefix: str, actor: ActorIdentity | None = None
    ) -> tuple[WorkflowResumeResult, str, ExecutionResult | None, bytes | None]:
        """Resume the workflow and, if it lands on CONFIRMED and a dispatcher is
        wired (M8), execute the domain write synchronously and reflect the real
        outcome in the reply. Shared by the fast and slow paths so a confirm
        resolved either way gets the same execution guarantee (and the same
        receipt-image behavior)."""
        result = await self._runtime.resume(loaded, resume_action)
        logger.info(
            "%s.resumed user=%s status=%s instance=%s",
            log_prefix,
            user_id,
            result.status.value,
            result.workflow_instance_id,
        )

        execution_result: ExecutionResult | None = None
        reply_image: bytes | None = None
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
            if self._receipt_builder is not None:
                reply_image = await self._receipt_builder.build(
                    result.confirmed_action, execution_result, actor
                )
        else:
            reply_text = render_resume_reply(result)

        return result, reply_text, execution_result, reply_image

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

        result, reply_text, execution_result, reply_image = await self._resume_and_render(
            user_id, loaded, decision.resume_action, log_prefix="interaction", actor=actor
        )
        return InteractionHandled(
            result=result,
            reply_text=reply_text,
            execution_result=execution_result,
            reply_image=reply_image,
            project_id=str(loaded.state.project_id) if loaded.state.project_id else None,
            site_id=str(loaded.state.site_id) if loaded.state.site_id else None,
        )

    def handle_category_tap(self, message: NormalizedMessage) -> str | None:
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
        reply_image: bytes | None = None

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
                result, reply_text, execution_result, reply_image = await self._resume_and_render(
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
                reply_image=reply_image,
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
