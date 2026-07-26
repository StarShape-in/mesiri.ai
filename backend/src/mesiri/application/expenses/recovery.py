"""Crash recovery for confirmed Expense workflows (M8-style).

Mirrors application/materials/recovery.py exactly — see its docstring for
the rationale (the only real crash window, idempotency-key safety,
deliberately scoped to the workflow_keys this executor understands).
Invocable manually or via a cron entry — not a background worker service.
"""

from __future__ import annotations

import logging

from mesiri.infrastructure.postgres.workflow_instance import list_confirmed_by_workflow_keys
from mesiri_contracts.application.results.execution_result import ExecutionResult
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.common.ids import new_id

from .handlers import RecordExpenseHandler

logger = logging.getLogger(__name__)

EXPENSE_WORKFLOW_KEYS = frozenset({WorkflowKey.EXPENSE_SUBMIT})


async def recover_confirmed_instances(
    db, handler: RecordExpenseHandler, workflow_keys: frozenset[WorkflowKey]
) -> list[ExecutionResult]:
    """Replay every CONFIRMED instance matching `workflow_keys` through `handler`."""
    loaded_instances = await list_confirmed_by_workflow_keys(
        db, [key.value for key in workflow_keys]
    )

    results: list[ExecutionResult] = []
    for loaded in loaded_instances:
        state = loaded.state
        if state.draft_action is None:
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
        result = await handler.handle_confirmed(confirmed)
        results.append(result)
    return results
