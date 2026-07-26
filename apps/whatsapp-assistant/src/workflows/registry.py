"""Workflow Registry — the lookup layer between Planner and LangGraph.

Planner never imports a workflow engine or a specific graph (architecture rule
#10); it returns only a workflow_key. This registry resolves that key to a
compiled graph. Graphs are compiled once and cached — a WhatsApp message must
never trigger a graph recompilation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mesiri_contracts.assistant.planner_decision import WorkflowKey

from .account_admin.graph import build_account_admin_graph
from .account_balance_query.graph import build_account_balance_query_graph
from .expense_capture.graph import build_expense_capture_graph
from .expense_query.graph import build_expense_query_graph
from .labour_update.graph import build_labour_attendance_graph
from .material import build_material_graph
from .material_inventory_query.graph import build_material_inventory_query_graph
from .petty_cash.graph import build_petty_cash_graph
from .reverse.graph import build_reverse_graph
from .transfer.graph import build_transfer_graph
from .who_am_i.graph import build_who_am_i_graph

_BUILDERS: dict[WorkflowKey, Callable[[], Any]] = {
    WorkflowKey.MATERIAL_RECEIPT: build_material_graph,
    WorkflowKey.MATERIAL_USAGE: build_material_graph,
    WorkflowKey.WHO_AM_I: build_who_am_i_graph,
    WorkflowKey.MATERIAL_INVENTORY_QUERY: build_material_inventory_query_graph,
    WorkflowKey.EXPENSE_SUBMIT: build_expense_capture_graph,
    WorkflowKey.ACCOUNT_ADMIN: build_account_admin_graph,
    WorkflowKey.ACCOUNT_BALANCE_QUERY: build_account_balance_query_graph,
    WorkflowKey.EXPENSE_QUERY: build_expense_query_graph,
    WorkflowKey.TRANSFER: build_transfer_graph,
    WorkflowKey.PETTY_CASH: build_petty_cash_graph,
    WorkflowKey.REVERSE: build_reverse_graph,
    WorkflowKey.LABOUR_ATTENDANCE: build_labour_attendance_graph,
}


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
        builder = _BUILDERS.get(key)
        if builder is None:
            return None
        graph = builder()
        self._compiled[key] = graph
        return graph
