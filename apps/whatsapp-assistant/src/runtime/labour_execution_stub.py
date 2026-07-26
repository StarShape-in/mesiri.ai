"""TEMPORARY stand-in for Labour persistence — delete when Phase 5 lands.

**This does not save anything.** It accepts a confirmed attendance, logs it,
and reports success so the WhatsApp conversation completes end to end.

Why it exists: the Labour module is being built conversation-first by explicit
decision (2026-07-26) — validate that the assistant understands attendance,
matches workers, asks only when it must, and previews correctly, *before*
committing to a database shape. Without a dispatcher registered for
RECORD_LABOUR_ATTENDANCE, `ActionTypeRoutingDispatcher` returns FAILED and the
user sees an error the moment they confirm, which makes the very thing we want
to test unobservable.

The deliberate trade: a supervisor who confirms an attendance on a build
running this stub is told it was recorded, and it was not. That is acceptable
**only** while Labour is behind an internal test flow. It must not reach real
site users. Two things make the gap loud rather than silent:

  - every confirmation logs at WARNING with the full attendance payload, so
    the control panel shows exactly what *would* have been written
  - the returned row id is prefixed `stub-`, so anything that stores or
    displays it is visibly holding a non-record

Replacing it is deliberately a one-line change in runtime/dependencies.py:
swap this for the real `LabourExecutionDispatcher` once Phase 5 exists. Do not
build on it — no caller should ever branch on its behaviour.
"""

from __future__ import annotations

import logging
from typing import Any

from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

logger = logging.getLogger(__name__)


def _summarize(fields: dict[str, Any]) -> str:
    """A one-line human summary for the log, so verifying behaviour doesn't
    mean reading raw JSON in the control panel."""
    raw_lines = fields.get("lines")
    lines = [line for line in raw_lines if isinstance(line, dict)] if isinstance(raw_lines, list) else []
    if not lines:
        return "no lines"
    parts: list[str] = []
    total = 0
    for line in lines:
        try:
            count = int(line.get("headcount", 1))
        except (TypeError, ValueError):
            count = 1
        total += count
        name = str(line.get("worker_name") or "").strip()
        trade = str(line.get("trade") or "").strip()
        if name:
            matched = "matched" if line.get("worker_id") else "temporary"
            parts.append(f"{name}({trade or '?'},{matched})")
        else:
            parts.append(f"{count}x{trade or '?'}")
    return f"{total} workers: " + ", ".join(parts)


class StubLabourExecutionDispatcher:
    """Satisfies the ExecutionDispatcher port without writing anything."""

    async def dispatch(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        draft = confirmed.draft_action
        logger.warning(
            "labour.execution_stub NOT PERSISTED workflow_instance_id=%s org=%s project=%s "
            "site=%s summary=%s fields=%s",
            confirmed.workflow_instance_id,
            draft.organization_id,
            draft.project_id,
            draft.site_id,
            _summarize(draft.fields),
            draft.fields,
        )
        return ExecutionResult(
            status=ExecutionStatus.SUCCEEDED,
            idempotency_key=confirmed.workflow_instance_id,
            material_row_id=f"stub-{confirmed.workflow_instance_id}",
        )
