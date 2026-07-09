"""MaterialExecutionDispatcher — implements interactions.ports.ExecutionDispatcher.

The only place that adapts the backend Application Handler to the shape
interactions/ depends on. Catches any unhandled exception from the Handler
and reports ExecutionStatus.FAILED instead of letting it propagate — the
Handler's transaction has already rolled back by the time an exception
reaches here, so the workflow is safely left at CONFIRMED, recoverable by
the recovery sweep. This is "the caller" referenced in the M8 plan's
rejection-vs-failure semantics.
"""

from __future__ import annotations

import logging

from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .handlers import ExecuteConfirmedMaterialActionHandler

logger = logging.getLogger(__name__)


class MaterialExecutionDispatcher:
    """Satisfies interactions.ports.ExecutionDispatcher by wrapping the Handler."""

    def __init__(self, handler: ExecuteConfirmedMaterialActionHandler) -> None:
        self._handler = handler

    async def dispatch(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        try:
            return await self._handler.handle(confirmed)
        except Exception:
            logger.exception(
                "material_execution.failed workflow_instance_id=%s",
                confirmed.workflow_instance_id,
            )
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                idempotency_key=confirmed.workflow_instance_id,
            )
