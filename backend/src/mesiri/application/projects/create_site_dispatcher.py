"""CreateSiteExecutionDispatcher — implements interactions.ports.ExecutionDispatcher.

Mirrors create_dispatcher.py's CreateProjectExecutionDispatcher.
"""

from __future__ import annotations

from mesiri.application.shared.execution import OperationalExecutionDispatcher
from mesiri_contracts.application.results.execution_result import ExecutionResult
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .handlers import CreateSiteHandler


class CreateSiteExecutionDispatcher(OperationalExecutionDispatcher):
    """Satisfies interactions.ports.ExecutionDispatcher by wrapping the Handler."""

    _LOG_LABEL = "site_create_execution"

    def __init__(self, handler: CreateSiteHandler) -> None:
        super().__init__(handler)
        self._handler: CreateSiteHandler = handler

    async def _execute(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        return await self._handler.handle_confirmed(confirmed)
