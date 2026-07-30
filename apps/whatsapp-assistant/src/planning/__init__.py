"""Composite-request plan layer (docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md).

Phase 1 only: the shared data structures and ordering logic. No decomposer,
no wiring into runtime/inbound_journey/process.py yet -- both are gated on
§4.4 of that doc (the entity-resolution layer's continuation building on
PlanStore rather than a standalone PendingReportStore generalization) and on
the decomposer itself (Phase 4), neither of which exist yet.
"""

from __future__ import annotations

from .ordering import PlanCycleError, PlanUnresolvedRefError, topological_order
from .plan import Plan, PlanOrigin, PlanStep, StepRef, StepStatus
from .plan_store import PlanStore

__all__ = [
    "Plan",
    "PlanOrigin",
    "PlanStep",
    "StepRef",
    "StepStatus",
    "PlanCycleError",
    "PlanUnresolvedRefError",
    "topological_order",
    "PlanStore",
]
