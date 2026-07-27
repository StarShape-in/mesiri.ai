"""Workflow Registry — the lookup layer between Planner and LangGraph.

Planner never imports a workflow engine or a specific graph (architecture rule
#10); it returns only a workflow_key. This registry resolves that key to a
compiled graph. Graphs are compiled once and cached — a WhatsApp message must
never trigger a graph recompilation.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import Enum
from typing import Any

from mesiri_contracts.assistant.planner_decision import WorkflowKey

from .account_admin.graph import build_account_admin_graph
from .account_balance_query.graph import build_account_balance_query_graph
from .activity_continuation.graph import build_activity_continuation_graph
from .expense_capture.graph import build_expense_capture_graph
from .expense_query.graph import build_expense_query_graph
from .labour_query.graph import build_labour_query_graph
from .labour_update.graph import build_labour_attendance_graph
from .material import build_material_graph
from .material_inventory_query.graph import build_material_inventory_query_graph
from .petty_cash.graph import build_petty_cash_graph
from .reverse.graph import build_reverse_graph
from .site_update.graph import build_activity_creation_graph
from .transfer.graph import build_transfer_graph
from .who_am_i.graph import build_who_am_i_graph


class WorkflowCategory(str, Enum):
    """Business domain a workflow belongs to.

    Registry-local metadata, deliberately *not* in mesiri_contracts: no
    Planner/Runtime contract crosses this boundary, so it must not become a
    wire-level enum that other services can couple to.
    """

    FINANCE = "finance"
    MATERIAL = "material"
    LABOUR = "labour"
    IDENTITY = "identity"
    PROGRESS = "progress"


@dataclass(frozen=True)
class WorkflowDefinition:
    """Everything the system knows about one workflow, in one place.

    Fields beyond ``builder`` carry no behaviour on their own -- they are the
    single source of truth that behavioural call sites read from, so that
    adding a workflow means editing one table rather than hunting down
    per-key sets scattered across modules.
    """

    key: WorkflowKey
    builder: Callable[[], Any]
    category: WorkflowCategory
    # Only answers a question; never produces a draft_action. Exempt from the
    # single-active pending-confirmation gate and completes without
    # AWAITING_CONFIRMATION. See workflows/runtime.py.
    is_informational: bool = False
    # May *sometimes* finish with no draft_action without that being a
    # failure. Implied by is_informational; also set on the mixed cases
    # (REVERSE, EXPENSE_SUBMIT, ACCOUNT_ADMIN) which still write a record most
    # of the time and so still respect the single-active gate.
    allows_completion_without_draft: bool = False

    def __post_init__(self) -> None:
        if self.is_informational and not self.allows_completion_without_draft:
            raise ValueError(
                f"{self.key}: an informational workflow never produces a draft, "
                "so allows_completion_without_draft must be True"
            )


def _define(
    key: WorkflowKey,
    builder: Callable[[], Any],
    category: WorkflowCategory,
    *,
    is_informational: bool = False,
    allows_completion_without_draft: bool = False,
) -> tuple[WorkflowKey, WorkflowDefinition]:
    """Build a (key, definition) pair, keeping the table below readable."""
    return key, WorkflowDefinition(
        key=key,
        builder=builder,
        category=category,
        is_informational=is_informational,
        # Informational implies it; spelled out here so the table stays flat.
        allows_completion_without_draft=allows_completion_without_draft or is_informational,
    )


_DEFINITIONS: dict[WorkflowKey, WorkflowDefinition] = dict(
    (
        _define(WorkflowKey.MATERIAL_RECEIPT, build_material_graph, WorkflowCategory.MATERIAL),
        _define(WorkflowKey.MATERIAL_USAGE, build_material_graph, WorkflowCategory.MATERIAL),
        _define(
            WorkflowKey.WHO_AM_I,
            build_who_am_i_graph,
            WorkflowCategory.IDENTITY,
            is_informational=True,
        ),
        _define(
            WorkflowKey.MATERIAL_INVENTORY_QUERY,
            build_material_inventory_query_graph,
            WorkflowCategory.MATERIAL,
            is_informational=True,
        ),
        _define(
            WorkflowKey.EXPENSE_SUBMIT,
            build_expense_capture_graph,
            WorkflowCategory.FINANCE,
            allows_completion_without_draft=True,
        ),
        _define(
            WorkflowKey.ACCOUNT_ADMIN,
            build_account_admin_graph,
            WorkflowCategory.FINANCE,
            allows_completion_without_draft=True,
        ),
        _define(
            WorkflowKey.ACCOUNT_BALANCE_QUERY,
            build_account_balance_query_graph,
            WorkflowCategory.FINANCE,
            is_informational=True,
        ),
        _define(
            WorkflowKey.EXPENSE_QUERY,
            build_expense_query_graph,
            WorkflowCategory.FINANCE,
            is_informational=True,
        ),
        _define(WorkflowKey.TRANSFER, build_transfer_graph, WorkflowCategory.FINANCE),
        _define(WorkflowKey.PETTY_CASH, build_petty_cash_graph, WorkflowCategory.FINANCE),
        _define(
            WorkflowKey.REVERSE,
            build_reverse_graph,
            WorkflowCategory.FINANCE,
            allows_completion_without_draft=True,
        ),
        _define(
            WorkflowKey.LABOUR_ATTENDANCE,
            build_labour_attendance_graph,
            WorkflowCategory.LABOUR,
        ),
        _define(
            WorkflowKey.LABOUR_QUERY,
            build_labour_query_graph,
            WorkflowCategory.LABOUR,
            is_informational=True,
        ),
        _define(
            WorkflowKey.SITE_UPDATE,
            build_activity_creation_graph,
            WorkflowCategory.PROGRESS,
        ),
        _define(
            WorkflowKey.ACTIVITY_CONTINUATION,
            build_activity_continuation_graph,
            WorkflowCategory.PROGRESS,
            allows_completion_without_draft=True,
        ),
    )
)


def get_definition(key: WorkflowKey) -> WorkflowDefinition | None:
    """Return the definition for ``key``, or None if the workflow isn't built yet."""
    return _DEFINITIONS.get(key)


def is_implemented(key: WorkflowKey) -> bool:
    """True when ``key`` has a graph wired up (some WorkflowKeys are declared but unbuilt)."""
    return key in _DEFINITIONS


def iter_definitions() -> Iterator[WorkflowDefinition]:
    """Every registered workflow, in registration order."""
    return iter(_DEFINITIONS.values())


def is_informational(key: WorkflowKey) -> bool:
    """True if ``key`` only answers a question and never produces a draft_action.

    False (not raise) for an unregistered key, so callers can use this as a
    plain predicate without checking is_implemented() first."""
    definition = _DEFINITIONS.get(key)
    return definition is not None and definition.is_informational


def allows_completion_without_draft(key: WorkflowKey) -> bool:
    """True if ``key`` may legitimately finish with no draft_action."""
    definition = _DEFINITIONS.get(key)
    return definition is not None and definition.allows_completion_without_draft


class WorkflowRegistry:
    """Resolves a WorkflowKey to a compiled graph, compiling (and caching) on first use."""

    def __init__(self) -> None:
        self._compiled: dict[WorkflowKey, Any] = {}

    def get_graph(self, key: WorkflowKey) -> Any | None:
        """Return the compiled graph for ``key``, or None if unmapped.

        Compiled exactly once per key for the lifetime of this registry —
        callers must not construct a new WorkflowRegistry per message.
        """
        if key in self._compiled:
            return self._compiled[key]
        definition = _DEFINITIONS.get(key)
        if definition is None:
            return None
        graph = definition.builder()
        self._compiled[key] = graph
        return graph
