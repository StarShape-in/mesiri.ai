"""LabourExecutionDispatcher — implements interactions.ports.ExecutionDispatcher.

Mirrors application/materials/dispatcher.py. Failure handling lives in
OperationalExecutionDispatcher (application/shared/execution.py) so it
cannot drift between operational modules — an unhandled exception from the
Handler reaches here only after its transaction has already rolled back, so
reporting FAILED (rather than re-raising) leaves the workflow safely at
CONFIRMED, recoverable by the recovery sweep.
"""

from __future__ import annotations

from mesiri.application.shared.execution import OperationalExecutionDispatcher
from mesiri_contracts.application.results.execution_result import ExecutionResult
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .handlers import ExecuteConfirmedLabourAttendanceHandler


class LabourExecutionDispatcher(OperationalExecutionDispatcher):
    """Satisfies interactions.ports.ExecutionDispatcher by wrapping the Handler."""

    _LOG_LABEL = "labour_execution"

    def __init__(self, handler: ExecuteConfirmedLabourAttendanceHandler) -> None:
        super().__init__(handler)
        self._handler: ExecuteConfirmedLabourAttendanceHandler = handler

    async def _execute(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        return await self._handler.handle(confirmed)
