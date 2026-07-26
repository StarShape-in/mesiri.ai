"""Execution scaffolding shared by every operational module.

Material, Expense and Finance had each written out the same two pieces of
infrastructure independently, and Labour would have made a fourth copy:

- **The dispatcher's error contract.** Catch anything the Handler didn't,
  log it against the workflow instance, and report FAILED rather than
  letting it propagate. This is load-bearing: by the time an exception
  reaches the dispatcher the Handler's transaction has already rolled back,
  so the workflow is safely left at CONFIRMED and the recovery sweep can
  replay it. Getting this wrong in one module and right in another is
  exactly the kind of divergence that stays invisible until a crash.

- **The recovery sweep.** Reconstruct a ConfirmedActionV2 from the durably
  persisted WorkflowStateV2 and replay it through the module's handler. Safe
  to run repeatedly because the idempotency key is the workflow_instance_id.

Deliberately *not* shared here, having compared all three modules:

- ``ResolutionResult`` — the three look alike but carry genuinely different
  payloads (``material_id``/``unit_id``, ``category_id``,
  ``target_account_id``). Only ``reasons`` is common; a base class for one
  field would be ceremony, not reuse.
- The execution repository ports — same three method names, but each is
  typed to its own command. A generic port would need a TypeVar and would
  document rather than remove the duplication.

Business logic stays in the modules. Only the plumbing lives here.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from backend.postgres.workflow_instance import list_confirmed_by_workflow_keys
from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.common.ids import new_id

logger = logging.getLogger(__name__)


class OperationalExecutionDispatcher:
    """Base for the per-module ``*ExecutionDispatcher`` classes.

    Satisfies ``interactions.ports.ExecutionDispatcher``. Subclasses supply a
    log label and say how to invoke their handler; everything about failure
    handling is inherited so it cannot drift between modules.

    Subclasses stay thin on purpose::

        class MaterialExecutionDispatcher(OperationalExecutionDispatcher):
            _LOG_LABEL = "material_execution"

            async def _execute(self, confirmed):
                return await self._handler.handle(confirmed)

    ``_execute`` exists rather than a fixed method name because the handlers
    genuinely disagree — Material exposes ``handle()`` while Expense and
    Finance expose ``handle_confirmed()``. Renaming one of them would be a
    behaviour-neutral change rippling through handlers, recovery and tests
    in a module this refactor otherwise doesn't touch; the indirection costs
    one line per module and keeps the blast radius at zero.
    """

    #: Prefix for the failure log line, e.g. "material_execution".
    _LOG_LABEL: str = "operational_execution"

    def __init__(self, handler: object) -> None:
        self._handler = handler

    async def dispatch(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        try:
            return await self._execute(confirmed)
        except Exception:
            logger.exception(
                "%s.failed workflow_instance_id=%s",
                self._LOG_LABEL,
                confirmed.workflow_instance_id,
            )
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                idempotency_key=confirmed.workflow_instance_id,
            )

    async def _execute(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        raise NotImplementedError


async def recover_confirmed_instances(
    db,
    *,
    execute: Callable[[ConfirmedActionV2], Awaitable[ExecutionResult]],
    workflow_keys: frozenset[WorkflowKey],
) -> list[ExecutionResult]:
    """Replay every CONFIRMED instance matching ``workflow_keys``.

    The crash window this closes: M7's ``resume()`` commits CONFIRMED in its
    own transaction, then the process dies before the Handler's transaction
    starts or commits. Recovery is a query, not a queue — the durable
    WorkflowStateV2 is enough to rebuild the ConfirmedActionV2 and replay it.
    The idempotency key (workflow_instance_id) makes replay safe whether or
    not an earlier attempt got as far as committing.

    Always called with the keys one executor understands — never an unscoped
    sweep over every CONFIRMED row in the shared workflow_instances table,
    since another module's rows are not this executor's to run.

    Invocable manually or from a cron entry; not a background worker.
    """
    loaded_instances = await list_confirmed_by_workflow_keys(
        db, [key.value for key in workflow_keys]
    )

    results: list[ExecutionResult] = []
    for loaded in loaded_instances:
        state = loaded.state
        if state.draft_action is None:
            # Shouldn't happen: resume() refuses to confirm without a draft.
            # Skip defensively rather than failing the whole sweep, which
            # would block every other recoverable instance behind it.
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
        results.append(await execute(confirmed))
    return results
