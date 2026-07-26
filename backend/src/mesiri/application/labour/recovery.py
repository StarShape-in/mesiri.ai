"""Crash recovery for confirmed Labour attendance workflows (M8).

Mirrors application/materials/recovery.py. The only real crash window: M7's
`resume()` commits CONFIRMED in its own transaction, then the process
crashes before the Handler's transaction ever starts or commits. Recovery is
a query, not a queue — reconstruct a ConfirmedActionV2 from the durably
persisted WorkflowStateV2 and replay the same Handler; the idempotency key
(workflow_instance_id) makes this always safe.

Deliberately scoped to WorkflowKey.LABOUR_ATTENDANCE only — never an
unscoped sweep over every CONFIRMED row in the generic workflow_instances
table.
"""

from __future__ import annotations

from mesiri.application.shared.execution import (
    recover_confirmed_instances as _recover_confirmed_instances,
)
from mesiri_contracts.application.results.execution_result import ExecutionResult
from mesiri_contracts.assistant.planner_decision import WorkflowKey

from .handlers import ExecuteConfirmedLabourAttendanceHandler

LABOUR_WORKFLOW_KEYS = frozenset({WorkflowKey.LABOUR_ATTENDANCE})


async def recover_confirmed_instances(
    db, handler: ExecuteConfirmedLabourAttendanceHandler, workflow_keys: frozenset[WorkflowKey]
) -> list[ExecutionResult]:
    """Replay every CONFIRMED Labour attendance instance matching `workflow_keys`.

    The sweep itself is shared (application/shared/execution.py) so its
    crash-window reasoning and replay safety live in one place; this wrapper
    only says which handler method to call.
    """
    return await _recover_confirmed_instances(
        db, execute=handler.handle, workflow_keys=workflow_keys
    )
