"""Workflow Runtime (M6) — executes LangGraph graphs selected via the Workflow Registry.

Single responsibility: run the graph a PlannerDecision routes to, produce a
DraftAction, and persist WorkflowState. Never touches SQL, AI providers, or
domain rules (architecture rule #11).
"""

from __future__ import annotations

from .ports import LoadedWorkflowInstance, SingleActiveConflict, WorkflowInstanceRepository
from .registry import WorkflowRegistry
from .runtime import (
    ResumeAction,
    WorkflowResumeResult,
    WorkflowResumeStatus,
    WorkflowRunResult,
    WorkflowRunStatus,
    WorkflowRuntime,
    log_workflow_run,
)

__all__ = [
    "WorkflowRegistry",
    "WorkflowRuntime",
    "WorkflowRunResult",
    "WorkflowRunStatus",
    "ResumeAction",
    "WorkflowResumeResult",
    "WorkflowResumeStatus",
    "LoadedWorkflowInstance",
    "WorkflowInstanceRepository",
    "SingleActiveConflict",
    "log_workflow_run",
]
