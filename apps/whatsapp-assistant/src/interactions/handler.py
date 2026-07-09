"""InteractionHandler — the fork between resuming a workflow and a new journey.

Sits after the identity gate and before the understanding pipeline. If the user
has an AWAITING_CONFIRMATION workflow and the reply is a confirmation
intent, it resumes the workflow and returns the reply — the AI pipeline is
never touched (a plain "yes" costs no tokens). Otherwise returns None and the
caller runs the normal understanding journey.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from mesiri_contracts.assistant.v2.interaction_spec import InteractionIntent
from workflows import WorkflowResumeResult, WorkflowRunResult, WorkflowRuntime

from .classifier import classify_reply
from .classifier_port import InteractionClassifierPort
from .policy import InteractionRoute, decide
from .response_handler import render_resume_reply, render_workflow_run_reply

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class InteractionHandled:
    """Returned when the message was handled as a workflow interaction."""

    result: WorkflowResumeResult | WorkflowRunResult
    reply_text: str
    unrelated_text: str | None = None


class InteractionHandler:
    def __init__(
        self,
        workflow_runtime: WorkflowRuntime,
        classifier: InteractionClassifierPort | None = None,
    ) -> None:
        self._runtime = workflow_runtime
        self._classifier = classifier

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

        result = await self._runtime.resume(loaded, decision.resume_action)
        logger.info(
            "interaction.resumed user=%s intent=%s status=%s instance=%s",
            user_id,
            intent.value,
            result.status.value,
            result.workflow_instance_id,
        )
        return InteractionHandled(result=result, reply_text=render_resume_reply(result))

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
                result = await self._runtime.resume(loaded, decision.resume_action)
                logger.info(
                    "interaction.slow_path.resumed user=%s intent=%s status=%s instance=%s",
                    user_id,
                    segment.intent.value,
                    result.status.value,
                    result.workflow_instance_id,
                )
                handled_result = result
                reply_text = render_resume_reply(result)
            continue

        unrelated_text = " ".join(unrelated_segments) if unrelated_segments else None

        if handled_result is not None and reply_text is not None:
            return InteractionHandled(
                result=handled_result, reply_text=reply_text, unrelated_text=unrelated_text
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
