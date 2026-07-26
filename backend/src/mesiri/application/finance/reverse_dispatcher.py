"""ReverseExecutionDispatcher — implements interactions.ports.ExecutionDispatcher.

Mirrors application/finance/transfer_dispatcher.py.
"""

from __future__ import annotations

import logging

from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .reverse_handler import ReverseTransactionHandler

logger = logging.getLogger(__name__)


class ReverseExecutionDispatcher:
    """Satisfies interactions.ports.ExecutionDispatcher by wrapping the Handler."""

    def __init__(self, handler: ReverseTransactionHandler) -> None:
        self._handler = handler

    async def dispatch(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        try:
            return await self._handler.handle_confirmed(confirmed)
        except Exception:
            logger.exception(
                "reverse_execution.failed workflow_instance_id=%s",
                confirmed.workflow_instance_id,
            )
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                idempotency_key=confirmed.workflow_instance_id,
            )
