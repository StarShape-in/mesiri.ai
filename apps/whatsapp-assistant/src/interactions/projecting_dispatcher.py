"""Wraps an ExecutionDispatcher to sync a newly-created Project/Site into the
context layer immediately after a successful confirmed WhatsApp write.

Every project/site created or updated through the REST routers
(projects/router.py) already calls context.projection_hooks.project_entity()
before responding -- without it, context_resolver (M4) can't find the new row
by name until context.reconcile_watchdog's periodic reconcile_all() catches
up (see that module's docstring: it exists precisely as the safety net for
paths that skip the immediate hook, not as the primary sync mechanism).
CreateProject/CreateSite's confirmed-command path is exactly such a path --
its execution repository lives in the backend package, which cannot import
apps/whatsapp-assistant/src/context (wrong dependency direction) -- so this
thin wrapper at the whatsapp-assistant boundary is where the hook belongs
instead, giving the WhatsApp path the same immediate visibility the REST
path has (e.g. so "create a site at Skyline Towers" right after creating
that project resolves it by name instead of waiting for the next reconcile
tick).
"""

from __future__ import annotations

import logging
import uuid

from context.identity_projection import EntityType
from context.projection_hooks import project_entity
from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .ports import ExecutionDispatcher

logger = logging.getLogger("mesiri.projecting_dispatcher")


class ProjectingExecutionDispatcher:
    """Satisfies ExecutionDispatcher by delegating to `inner`, then -- only on
    SUCCEEDED -- projecting the new row's id into the context layer as
    `entity_type`. Best-effort: project_entity already swallows and logs its
    own failures (see its docstring), so a projection failure here can never
    turn a successful domain write into a failed one."""

    def __init__(self, inner: ExecutionDispatcher, entity_type: EntityType) -> None:
        self._inner = inner
        self._entity_type = entity_type

    async def dispatch(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        result = await self._inner.dispatch(confirmed)
        if result.status == ExecutionStatus.SUCCEEDED and result.material_row_id:
            try:
                await project_entity(self._entity_type, uuid.UUID(result.material_row_id))
            except Exception:  # noqa: BLE001
                logger.exception(
                    "projecting_dispatcher.projection_failed entity_type=%s entity_id=%s",
                    self._entity_type,
                    result.material_row_id,
                )
        return result
