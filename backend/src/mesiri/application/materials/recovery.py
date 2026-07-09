"""Crash recovery for confirmed Material workflows (M8).

The only real crash window: M7's `resume()` commits CONFIRMED in its own
transaction, then the process crashes before the Handler's transaction ever
starts or commits. Recovery is a query, not a queue — reconstruct a
ConfirmedActionV2 from the durably-persisted WorkflowStateV2 and replay the
same Handler; the idempotency key (workflow_instance_id) makes this always
safe, whether or not a prior attempt actually got as far as committing.

Deliberately scoped to the workflow_keys this executor understands — never
an unscoped sweep over every CONFIRMED row in the generic workflow_instances
table (a future Expense/Equipment/Labour executor gets its own scoped call).

Invocable manually or via a cron entry — not a background worker service
(out of scope for this milestone).
"""

from __future__ import annotations

import logging

from backend.postgres.workflow_instance import list_confirmed_by_workflow_keys
from mesiri_contracts.application.results.execution_result import ExecutionResult
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.common.ids import new_id

from .handlers import ExecuteConfirmedMaterialActionHandler

logger = logging.getLogger(__name__)

MATERIAL_WORKFLOW_KEYS = frozenset({WorkflowKey.MATERIAL_RECEIPT, WorkflowKey.MATERIAL_USAGE})


async def recover_confirmed_instances(
    db, handler: ExecuteConfirmedMaterialActionHandler, workflow_keys: frozenset[WorkflowKey]
) -> list[ExecutionResult]:
    """Replay every CONFIRMED instance matching `workflow_keys` through `handler`."""
    loaded_instances = await list_confirmed_by_workflow_keys(
        db, [key.value for key in workflow_keys]
    )

    results: list[ExecutionResult] = []
    for loaded in loaded_instances:
        state = loaded.state
        if state.draft_action is None:
            # Shouldn't happen: resume() refuses to confirm without a draft.
            # Defensive skip rather than crashing the whole sweep.
            logger.error(
                "recovery.confirmed_without_draft workflow_instance_id=%s",
                state.workflow_instance_id,
            )
            continue

        confirmed = ConfirmedActionV2(
            confirmed_action_id=new_id("confirmed"),
            workflow_instance_id=state.workflow_instance_id,
            correlation_id=state.correlation_id,
            draft_action=state.draft_action,
            confirmed_by_user_id=state.user_id,
        )
        result = await handler.handle(confirmed)
        results.append(result)
    return results
