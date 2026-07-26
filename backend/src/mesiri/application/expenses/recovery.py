"""Crash recovery for confirmed Expense workflows (M8-style).

Mirrors application/materials/recovery.py exactly — see its docstring for
the rationale (the only real crash window, idempotency-key safety,
deliberately scoped to the workflow_keys this executor understands).
Invocable manually or via a cron entry — not a background worker service.
"""

from __future__ import annotations

from mesiri.application.shared.execution import (
    recover_confirmed_instances as _recover_confirmed_instances,
)
from mesiri_contracts.application.results.execution_result import ExecutionResult
from mesiri_contracts.assistant.planner_decision import WorkflowKey

from .handlers import RecordExpenseHandler

EXPENSE_WORKFLOW_KEYS = frozenset({WorkflowKey.EXPENSE_SUBMIT})


async def recover_confirmed_instances(
    db, handler: RecordExpenseHandler, workflow_keys: frozenset[WorkflowKey]
) -> list[ExecutionResult]:
    """Replay every CONFIRMED Expense instance matching `workflow_keys`.

    The sweep itself is shared (application/shared/execution.py) so its
    crash-window reasoning and replay safety live in one place; this wrapper
    only says which handler method to call.
    """
    return await _recover_confirmed_instances(
        db, execute=handler.handle_confirmed, workflow_keys=workflow_keys
    )
