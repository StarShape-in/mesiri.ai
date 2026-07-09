"""InteractionHandler — the fork between resuming a workflow and a new journey.

Sits after the identity gate and before the understanding pipeline. If the user
has an AWAITING_CONFIRMATION workflow and the reply is a confirmation
intent, it resumes the workflow and returns the reply — the AI pipeline is
never touched (a plain "yes" costs no tokens). Otherwise returns None and the
caller runs the normal understanding journey.

When a CONFIRM resolves to WorkflowResumeStatus.CONFIRMED and a dispatcher is
wired (M8), the confirmed action is executed synchronously in the same
request and the reply reflects the real domain outcome (SUCCEEDED/REJECTED/
FAILED) rather than optimistically assuming the domain write happened.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from mesiri_contracts.application.results.execution_result import ExecutionResult
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from workflows import WorkflowResumeResult, WorkflowResumeStatus, WorkflowRuntime

from .classifier import classify_reply
from .policy import InteractionRoute, decide
from .ports import ExecutionDispatcher
from .response_handler import render_execution_reply, render_resume_reply

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class InteractionHandled:
    """Returned when the message was handled as a workflow interaction."""

    result: WorkflowResumeResult
    reply_text: str
    execution_result: ExecutionResult | None = None

class InteractionHandler:
    def __init__(
        self,
        workflow_runtime: WorkflowRuntime,
        dispatcher: ExecutionDispatcher | None = None,
    ) -> None:
        self._runtime = workflow_runtime
        self._dispatcher = dispatcher

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

        execution_result: ExecutionResult | None = None
        if result.status is WorkflowResumeStatus.CONFIRMED and self._dispatcher is not None:
            assert result.confirmed_action is not None
            execution_result = await self._dispatcher.dispatch(result.confirmed_action)
            logger.info(
                "interaction.executed user=%s status=%s instance=%s",
                user_id,
                execution_result.status.value,
                result.workflow_instance_id,
            )
            reply_text = render_execution_reply(execution_result)
        else:
            reply_text = render_resume_reply(result)

        return InteractionHandled(
            result=result, reply_text=reply_text, execution_result=execution_result
        )
