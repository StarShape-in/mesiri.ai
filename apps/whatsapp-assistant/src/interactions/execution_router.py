"""Routes a confirmed action to the dispatcher registered for its action_type.

InteractionHandler only ever holds one ExecutionDispatcher (see handler.py).
As more workflows go through the M8 confirm-execute path (Materials, now
Expense), this composes multiple domain dispatchers behind that single port
instead of teaching InteractionHandler about domain-specific action types.
"""

from __future__ import annotations

import logging

from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .ports import ExecutionDispatcher

logger = logging.getLogger(__name__)


class ActionTypeRoutingDispatcher:
    """Satisfies ExecutionDispatcher by delegating to the dispatcher registered
    for confirmed.draft_action.action_type."""

    def __init__(self, dispatchers: dict[DraftActionType, ExecutionDispatcher]) -> None:
        self._dispatchers = dispatchers

    async def dispatch(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        dispatcher = self._dispatchers.get(confirmed.draft_action.action_type)
        if dispatcher is None:
            logger.error(
                "execution_router.no_dispatcher action_type=%s workflow_instance_id=%s",
                confirmed.draft_action.action_type,
                confirmed.workflow_instance_id,
            )
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                idempotency_key=confirmed.workflow_instance_id,
            )
        return await dispatcher.dispatch(confirmed)
