"""CreateUserExecutionDispatcher — implements interactions.ports.ExecutionDispatcher.

Mirrors application/projects/add_member_dispatcher.py's
AddProjectMemberExecutionDispatcher.
"""

from __future__ import annotations

from mesiri.application.shared.execution import OperationalExecutionDispatcher
from mesiri_contracts.application.results.execution_result import ExecutionResult
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .handlers import CreateUserHandler


class CreateUserExecutionDispatcher(OperationalExecutionDispatcher):
    """Satisfies interactions.ports.ExecutionDispatcher by wrapping the Handler."""

    _LOG_LABEL = "create_user_execution"

    def __init__(self, handler: CreateUserHandler) -> None:
        super().__init__(handler)
        self._handler: CreateUserHandler = handler

    async def _execute(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        return await self._handler.handle_confirmed(confirmed)
