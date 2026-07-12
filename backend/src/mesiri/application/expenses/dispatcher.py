"""ExpenseExecutionDispatcher — implements interactions.ports.ExecutionDispatcher.

Mirrors application/materials/dispatcher.py. Catches any unhandled exception
from the Handler and reports ExecutionStatus.FAILED instead of letting it
propagate — the Handler's transaction has already rolled back by the time an
exception reaches here, so the workflow is safely left at CONFIRMED,
recoverable by the recovery sweep (recovery.py).
"""

from __future__ import annotations

import logging

from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .handlers import RecordExpenseHandler

logger = logging.getLogger(__name__)


class ExpenseExecutionDispatcher:
    """Satisfies interactions.ports.ExecutionDispatcher by wrapping the Handler."""

    def __init__(self, handler: RecordExpenseHandler) -> None:
        self._handler = handler

    async def dispatch(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        try:
            return await self._handler.handle_confirmed(confirmed)
        except Exception:
            logger.exception(
                "expense_execution.failed workflow_instance_id=%s",
                confirmed.workflow_instance_id,
            )
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                idempotency_key=confirmed.workflow_instance_id,
            )
