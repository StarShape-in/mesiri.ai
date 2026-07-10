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

from mesiri_contracts.application.results.execution_result import ExecutionResult
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from mesiri_contracts.assistant.v2.interaction_spec import InteractionIntent
from workflows import WorkflowResumeResult, WorkflowResumeStatus, WorkflowRunResult, WorkflowRuntime

from .classifier import classify_reply
from .classifier_port import InteractionClassifierPort
from .policy import InteractionRoute, decide
from .ports import ExecutionDispatcher
from .response_handler import render_execution_reply, render_resume_reply, render_workflow_run_reply

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class InteractionHandled:
    """Returned when the message was handled as a workflow interaction."""

    result: WorkflowResumeResult | WorkflowRunResult
    reply_text: str
    execution_result: ExecutionResult | None = None
    unrelated_text: str | None = None


class InteractionHandler:
    def __init__(
        self,
        workflow_runtime: WorkflowRuntime,
        classifier: InteractionClassifierPort | None = None,
        dispatcher: ExecutionDispatcher | None = None,
    ) -> None:
        self._runtime = workflow_runtime
        self._classifier = classifier
        self._dispatcher = dispatcher

    async def _resume_and_render(
        self, user_id: str, loaded, resume_action, *, log_prefix: str
    ) -> tuple[WorkflowResumeResult, str, ExecutionResult | None]:
        """Resume the workflow and, if it lands on CONFIRMED and a dispatcher is
        wired (M8), execute the domain write synchronously and reflect the real
        outcome in the reply. Shared by the fast and slow paths so a confirm
        resolved either way gets the same execution guarantee."""
        result = await self._runtime.resume(loaded, resume_action)
        logger.info(
            "%s.resumed user=%s status=%s instance=%s",
            log_prefix,
            user_id,
            result.status.value,
            result.workflow_instance_id,
        )

        execution_result: ExecutionResult | None = None
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
        else:
            reply_text = render_resume_reply(result)

        return result, reply_text, execution_result

    async def handle_fast_path(
        self, user_id: str, message: NormalizedMessage
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

        result, reply_text, execution_result = await self._resume_and_render(
            user_id, loaded, decision.resume_action, log_prefix="interaction"
        )
        return InteractionHandled(
            result=result, reply_text=reply_text, execution_result=execution_result
        )

    async def handle_slow_path(
        self,
        user_id: str,
        message: NormalizedMessage,
        original_text: str,
        translated_text: str | None,
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
                result, reply_text, execution_result = await self._resume_and_render(
                    user_id, loaded, decision.resume_action, log_prefix="interaction.slow_path"
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
