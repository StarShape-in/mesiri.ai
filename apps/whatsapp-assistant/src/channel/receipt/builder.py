"""Concrete ReceiptBuilder — satisfies interactions.ports.ReceiptBuilder.

The only place that wires ConfirmedActionV2 + ExecutionResult + ActorIdentity
into the pure data.py mapper, then the template + renderer. Catches every
exception (the port's contract: never break the confirm flow over a
rendering failure) and returns None to degrade to a text-only confirmation.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .data import build_receipt_data
from .render import ReceiptRenderer
from .template import render_html

logger = logging.getLogger(__name__)


class RecordReceiptBuilder:
    """Builds the receipt card for ANY confirmed record.

    Named for materials once, when that was all there was. It has since served
    expense, and now labour attendance -- so the old name pointed anyone
    debugging a wrong-looking expense or attendance receipt away from the one
    file that renders it. `build_receipt_data` branches per action type; this
    class is type-agnostic.
    """

    def __init__(self, renderer: ReceiptRenderer) -> None:
        self._renderer = renderer

    async def build(self, confirmed: ConfirmedActionV2, execution: ExecutionResult, actor) -> bytes | None:
        if execution.status not in (ExecutionStatus.SUCCEEDED, ExecutionStatus.ALREADY_EXECUTED):
            return None
        if execution.material_row_id is None:
            return None
        try:
            data = build_receipt_data(
                confirmed.draft_action,
                material_row_id=execution.material_row_id,
                reporter_name=actor.full_name if actor else None,
                projects=actor.projects if actor else [],
                sites=actor.sites if actor else [],
                confirmed_at=datetime.now(UTC),
            )
            html = render_html(data)
            return await self._renderer.render_png(html)
        except Exception:
            logger.exception(
                "receipt.render_failed correlation_id=%s workflow_instance_id=%s",
                confirmed.correlation_id,
                confirmed.workflow_instance_id,
            )
            return None
