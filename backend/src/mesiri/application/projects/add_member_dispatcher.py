"""AddProjectMemberExecutionDispatcher — implements interactions.ports.ExecutionDispatcher.

Mirrors create_site_dispatcher.py's CreateSiteExecutionDispatcher.
"""

from __future__ import annotations

from mesiri.application.shared.execution import OperationalExecutionDispatcher
from mesiri_contracts.application.results.execution_result import ExecutionResult
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .handlers import AddProjectMemberHandler


class AddProjectMemberExecutionDispatcher(OperationalExecutionDispatcher):
    """Satisfies interactions.ports.ExecutionDispatcher by wrapping the Handler."""

    _LOG_LABEL = "add_project_member_execution"

    def __init__(self, handler: AddProjectMemberHandler) -> None:
        super().__init__(handler)
        self._handler: AddProjectMemberHandler = handler

    async def _execute(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        return await self._handler.handle_confirmed(confirmed)
