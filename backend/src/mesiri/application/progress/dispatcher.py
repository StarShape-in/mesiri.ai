"""Progress ExecutionDispatchers — implement interactions.ports.ExecutionDispatcher.

Mirrors application/labour/dispatcher.py and application/materials/dispatcher.py.
Failure handling lives in OperationalExecutionDispatcher (application/shared/
execution.py) so it cannot drift between operational modules.

Two dispatchers, not one, matching the two Handlers (plan ADR-D12: each
workflow key gets its own graph, its own Handler, and its own dispatcher —
the same one-capability-per-unit convention used throughout this repository).
"""

from __future__ import annotations

from mesiri.application.shared.execution import OperationalExecutionDispatcher
from mesiri_contracts.application.results.execution_result import ExecutionResult
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .handlers import (
    ExecuteConfirmedAddProgressUpdateHandler,
    ExecuteConfirmedCloseSiteIssueHandler,
    ExecuteConfirmedCreateActivityHandler,
    ExecuteConfirmedReportSiteIssueHandler,
)


class CreateActivityExecutionDispatcher(OperationalExecutionDispatcher):
    """Satisfies interactions.ports.ExecutionDispatcher by wrapping the Handler."""

    _LOG_LABEL = "create_activity_execution"

    def __init__(self, handler: ExecuteConfirmedCreateActivityHandler) -> None:
        super().__init__(handler)
        self._handler: ExecuteConfirmedCreateActivityHandler = handler

    async def _execute(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        return await self._handler.handle(confirmed)


class AddProgressUpdateExecutionDispatcher(OperationalExecutionDispatcher):
    """Satisfies interactions.ports.ExecutionDispatcher by wrapping the Handler."""

    _LOG_LABEL = "add_progress_update_execution"

    def __init__(self, handler: ExecuteConfirmedAddProgressUpdateHandler) -> None:
        super().__init__(handler)
        self._handler: ExecuteConfirmedAddProgressUpdateHandler = handler

    async def _execute(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        return await self._handler.handle(confirmed)


class ReportSiteIssueExecutionDispatcher(OperationalExecutionDispatcher):
    """Satisfies interactions.ports.ExecutionDispatcher by wrapping the Handler."""

    _LOG_LABEL = "report_site_issue_execution"

    def __init__(self, handler: ExecuteConfirmedReportSiteIssueHandler) -> None:
        super().__init__(handler)
        self._handler: ExecuteConfirmedReportSiteIssueHandler = handler

    async def _execute(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        return await self._handler.handle(confirmed)


class CloseSiteIssueExecutionDispatcher(OperationalExecutionDispatcher):
    """Satisfies interactions.ports.ExecutionDispatcher by wrapping the Handler."""

    _LOG_LABEL = "close_site_issue_execution"

    def __init__(self, handler: ExecuteConfirmedCloseSiteIssueHandler) -> None:
        super().__init__(handler)
        self._handler: ExecuteConfirmedCloseSiteIssueHandler = handler

    async def _execute(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        return await self._handler.handle(confirmed)
