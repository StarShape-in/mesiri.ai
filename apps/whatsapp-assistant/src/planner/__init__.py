"""Planner (M5) — routes a CanonicalEvent to a PlannerDecision.

Single responsibility: decide which workflow_key (if any) should run next.
Must never import a workflow engine, LangGraph, or any specific graph
(architecture rule #10) — it returns only a routing key.
"""

from __future__ import annotations

from .planner import Planner, log_planner_decision

__all__ = ["Planner", "log_planner_decision"]
