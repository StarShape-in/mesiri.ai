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
from workflows import WorkflowResumeResult, WorkflowResumeStatus, WorkflowRuntime

from .classifier import classify_reply
from .policy import InteractionRoute, decide
from .response_handler import render_resume_reply

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class InteractionHandled:
    """Returned when the message was handled as a workflow interaction."""

    result: WorkflowResumeResult
    reply_text: str





class InteractionHandler:
    def __init__(self, workflow_runtime: WorkflowRuntime) -> None:
        self._runtime = workflow_runtime

    async def handle(
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
