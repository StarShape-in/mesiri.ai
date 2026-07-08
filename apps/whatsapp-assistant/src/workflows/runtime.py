"""Workflow Runtime (M6) — executes a compiled graph from a PlannerDecision.

Orchestration only: state, transitions, and the confirmation handoff. Never
touches SQL, repositories, domain rules, or AI providers (architecture rule
#11 + layer-ownership table). The runtime enforces its own precondition (only
a START_WORKFLOW decision may reach ``start()``) rather than trusting callers.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from enum import Enum

from mesiri_contracts.assistant.planner_decision import PlannerDecisionType, WorkflowKey
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2
from mesiri_contracts.context.enums import WorkflowPhase

from .ports import WorkflowInstanceRepository
from .registry import WorkflowRegistry
from .state import WorkflowGraphState

logger = logging.getLogger(__name__)


class WorkflowRunStatus(str, Enum):
    STARTED = "started"
    NO_GRAPH = "no_graph"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class WorkflowRunResult:
    """A discriminated result — invariants enforced per status, not an ad-hoc
    nullable dataclass."""

    status: WorkflowRunStatus
    workflow_key: WorkflowKey
    correlation_id: str
    workflow_instance_id: str | None = None
    draft_action: DraftActionV2 | None = None
    pending_prompt: str | None = None

    def __post_init__(self) -> None:
        carries_started_fields = (
            self.workflow_instance_id is not None
            or self.draft_action is not None
            or self.pending_prompt is not None
        )
        if self.status is WorkflowRunStatus.STARTED:
            if not (self.workflow_instance_id and self.draft_action and self.pending_prompt):
                raise ValueError(
                    "STARTED requires workflow_instance_id, draft_action, and pending_prompt"
                )
        elif carries_started_fields:
            raise ValueError(
                f"{self.status.value} must not carry workflow_instance_id/draft_action/pending_prompt"
            )

    @classmethod
    def started(
        cls,
        *,
        workflow_key: WorkflowKey,
        correlation_id: str,
        workflow_instance_id: str,
        draft_action: DraftActionV2,
        pending_prompt: str,
    ) -> WorkflowRunResult:
        return cls(
            status=WorkflowRunStatus.STARTED,
            workflow_key=workflow_key,
            correlation_id=correlation_id,
            workflow_instance_id=workflow_instance_id,
            draft_action=draft_action,
            pending_prompt=pending_prompt,
        )

    @classmethod
    def no_graph(cls, *, workflow_key: WorkflowKey, correlation_id: str) -> WorkflowRunResult:
        return cls(status=WorkflowRunStatus.NO_GRAPH, workflow_key=workflow_key, correlation_id=correlation_id)

    @classmethod
    def failed(cls, *, workflow_key: WorkflowKey, correlation_id: str) -> WorkflowRunResult:
        return cls(status=WorkflowRunStatus.FAILED, workflow_key=workflow_key, correlation_id=correlation_id)


class WorkflowRuntime:
    """Starts a workflow graph from a PlannerDecision + CanonicalEvent."""

    def __init__(self, registry: WorkflowRegistry, repo: WorkflowInstanceRepository) -> None:
        self._registry = registry
        self._repo = repo

    async def start(self, decision: PlannerDecisionV2, event: CanonicalEventV2) -> WorkflowRunResult:
        # Defensive precondition: the runtime is a boundary and enforces this
        # itself rather than relying exclusively on the caller (inbound_journey
        # already only calls start() for START_WORKFLOW, but must not be the
        # only thing standing between a bad decision and a broken graph run).
        if decision.decision_type is not PlannerDecisionType.START_WORKFLOW or decision.workflow_key is None:
            raise ValueError(
                "WorkflowRuntime.start() requires a START_WORKFLOW decision with a workflow_key, "
                f"got decision_type={decision.decision_type!r} workflow_key={decision.workflow_key!r}"
            )
        workflow_key = decision.workflow_key

        # Look up the graph BEFORE minting any identity: an unmapped key must
        # never generate an orphaned workflow_instance_id.
        graph = self._registry.get_graph(workflow_key)
        if graph is None:
            logger.warning("workflow.no_graph workflow_key=%s", workflow_key.value)
            return WorkflowRunResult.no_graph(workflow_key=workflow_key, correlation_id=event.correlation_id)

        workflow_instance_id = str(uuid.uuid4())
        graph_state: WorkflowGraphState = {
            "workflow_instance_id": workflow_instance_id,
            "workflow_key": workflow_key.value,
            "correlation_id": event.correlation_id,
            "organization_id": event.organization_id,
            "user_id": event.user_id,
            "project_id": event.project_id,
            "site_id": event.site_id,
            "collected_fields": dict(event.fields),
        }

        try:
            result_state = await graph.ainvoke(graph_state)
        except Exception:
            logger.exception(
                "workflow.run_failed workflow_key=%s workflow_instance_id=%s",
                workflow_key.value,
                workflow_instance_id,
            )
            return WorkflowRunResult.failed(workflow_key=workflow_key, correlation_id=event.correlation_id)

        draft_action: DraftActionV2 | None = result_state.get("draft_action")
        pending_prompt: str | None = result_state.get("pending_prompt")
        if draft_action is None or pending_prompt is None:
            logger.error(
                "workflow.incomplete_result workflow_key=%s workflow_instance_id=%s",
                workflow_key.value,
                workflow_instance_id,
            )
            return WorkflowRunResult.failed(workflow_key=workflow_key, correlation_id=event.correlation_id)

        state = WorkflowStateV2(
            workflow_instance_id=workflow_instance_id,
            workflow_key=workflow_key,
            correlation_id=event.correlation_id,
            organization_id=event.organization_id,
            user_id=event.user_id,
            project_id=event.project_id,
            site_id=event.site_id,
            phase=WorkflowPhase.AWAITING_CONFIRMATION,
            collected_fields=dict(event.fields),
            draft_action=draft_action,
            pending_prompt=pending_prompt,
        )

        try:
            await self._repo.save(state)
        except Exception:
            logger.exception("workflow.save_failed workflow_instance_id=%s", workflow_instance_id)
            return WorkflowRunResult.failed(workflow_key=workflow_key, correlation_id=event.correlation_id)

        return WorkflowRunResult.started(
            workflow_key=workflow_key,
            correlation_id=event.correlation_id,
            workflow_instance_id=workflow_instance_id,
            draft_action=draft_action,
            pending_prompt=pending_prompt,
        )


def log_workflow_run(result: WorkflowRunResult) -> None:
    """Log the WorkflowRunResult for development visibility (not user-facing)."""
    logger.info(
        "WorkflowRun correlation_id=%s workflow_key=%s status=%s workflow_instance_id=%s",
        result.correlation_id,
        result.workflow_key.value,
        result.status.value,
        result.workflow_instance_id or "none",
    )
