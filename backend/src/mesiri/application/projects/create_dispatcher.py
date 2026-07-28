"""CreateProjectExecutionDispatcher — implements interactions.ports.ExecutionDispatcher.

Mirrors application/finance/dispatcher.py's AccountAdminExecutionDispatcher.
Catches any unhandled exception from the Handler and reports
ExecutionStatus.FAILED instead of letting it propagate — the Handler's
transaction has already rolled back by the time an exception reaches here,
so the workflow is safely left at CONFIRMED, recoverable by the recovery
sweep.
"""

from __future__ import annotations

from mesiri.application.shared.execution import OperationalExecutionDispatcher
from mesiri_contracts.application.results.execution_result import ExecutionResult
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .handlers import CreateProjectHandler


class CreateProjectExecutionDispatcher(OperationalExecutionDispatcher):
    """Satisfies interactions.ports.ExecutionDispatcher by wrapping the Handler."""

    _LOG_LABEL = "project_create_execution"

    def __init__(self, handler: CreateProjectHandler) -> None:
        super().__init__(handler)
        self._handler: CreateProjectHandler = handler

    async def _execute(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        return await self._handler.handle_confirmed(confirmed)
