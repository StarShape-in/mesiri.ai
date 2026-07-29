"""CreateAutomationExecutionDispatcher -- implements interactions.ports.ExecutionDispatcher.

Mirrors application/projects/create_site_dispatcher.py's
CreateSiteExecutionDispatcher.
"""

from __future__ import annotations

from mesiri.application.shared.execution import OperationalExecutionDispatcher
from mesiri_contracts.application.results.execution_result import ExecutionResult
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .handlers import CreateAutomationHandler


class CreateAutomationExecutionDispatcher(OperationalExecutionDispatcher):
    """Satisfies interactions.ports.ExecutionDispatcher by wrapping the Handler."""

    _LOG_LABEL = "automation_create_execution"

    def __init__(self, handler: CreateAutomationHandler) -> None:
        super().__init__(handler)
        self._handler: CreateAutomationHandler = handler

    async def _execute(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        return await self._handler.handle_confirmed(confirmed)
