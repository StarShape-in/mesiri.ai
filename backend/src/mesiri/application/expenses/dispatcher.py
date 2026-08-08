"""ExpenseExecutionDispatcher — implements interactions.ports.ExecutionDispatcher.

Mirrors application/materials/dispatcher.py. Catches any unhandled exception
from the Handler and reports ExecutionStatus.FAILED instead of letting it
propagate — the Handler's transaction has already rolled back by the time an
exception reaches here, so the workflow is safely left at CONFIRMED,
recoverable by the recovery sweep (recovery.py).
"""

from __future__ import annotations

from mesiri.application.shared.execution import OperationalExecutionDispatcher
from mesiri_contracts.application.results.execution_result import ExecutionResult
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .handlers import RecordExpenseHandler


class ExpenseExecutionDispatcher(OperationalExecutionDispatcher):
    """Satisfies interactions.ports.ExecutionDispatcher by wrapping the Handler.

    Failure handling lives in OperationalExecutionDispatcher so it cannot
    drift between operational modules -- see that class's docstring for why
    reporting FAILED (rather than raising) leaves the workflow recoverable.
    """

    _LOG_LABEL = "expense_execution"

    def __init__(self, handler: RecordExpenseHandler) -> None:
        super().__init__(handler)
        self._handler: RecordExpenseHandler = handler

    async def _execute(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        return await self._handler.handle_confirmed(confirmed)
