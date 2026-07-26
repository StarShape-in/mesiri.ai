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
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.assistant.v2.interaction_spec import FieldCorrection
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2
from mesiri_contracts.common.ids import new_id
from mesiri_contracts.context.enums import WorkflowPhase

from .ports import LoadedWorkflowInstance, SingleActiveConflict, WorkflowInstanceRepository
from .registry import WorkflowRegistry
from .state import WorkflowGraphState

logger = logging.getLogger(__name__)

# Workflows that only answer a question and never produce a draft_action --
# no business record to confirm, so they are exempt from the single-active
# pending-confirmation gate and complete without AWAITING_CONFIRMATION.
#
# WorkflowKey.REVERSE and WorkflowKey.EXPENSE_SUBMIT are mixed cases, not
# purely informational: when runtime/inbound_journey.py's seeding step finds
# nothing to reverse (no recent expense/transfer of the requested kind),
# workflows/reverse/nodes.py omits draft_action and completes with a
# "nothing to reverse" reply -- exactly the same no-draft outcome as a real
# informational workflow. Likewise, workflows/expense_capture/nodes.py's
# `check_duplicate` (Finance Module Slice 8) omits draft_action when the
# user answers "no" to a "looks like a duplicate, record anyway?" prompt.
# When a target *is* found (or the duplicate answer is "yes"), the same
# graph still produces a draft_action and the normal AWAITING_CONFIRMATION
# path below runs unaffected (this set is only consulted when draft_action
# is None).
_INFORMATIONAL_WORKFLOW_KEYS = frozenset(
    {
        WorkflowKey.WHO_AM_I,
        WorkflowKey.MATERIAL_INVENTORY_QUERY,
        WorkflowKey.ACCOUNT_BALANCE_QUERY,
        WorkflowKey.EXPENSE_QUERY,
        WorkflowKey.REVERSE,
        WorkflowKey.EXPENSE_SUBMIT,
    }
)


class WorkflowRunStatus(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    NO_GRAPH = "no_graph"
    FAILED = "failed"
    # A new actionable intent arrived while the user already has a confirmation
    # pending (single-active invariant). Carries the *existing* pending prompt.
    BLOCKED_PENDING_CONFIRMATION = "blocked_pending_confirmation"
    # A node set awaiting_slot (e.g. "which account?") -- persisted as
    # COLLECTING_FIELDS, not yet a draft awaiting confirmation. See Finance
    # Module Slice 1 / workflows/slots.py.
    AWAITING_INPUT = "awaiting_input"


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
        if self.status is WorkflowRunStatus.STARTED:
            if not (self.workflow_instance_id and self.draft_action and self.pending_prompt):
                raise ValueError(
                    "STARTED requires workflow_instance_id, draft_action, and pending_prompt"
                )
        elif self.status is WorkflowRunStatus.COMPLETED:
            if not self.pending_prompt:
                raise ValueError("COMPLETED requires pending_prompt")
        elif self.status is WorkflowRunStatus.BLOCKED_PENDING_CONFIRMATION:
            if not self.pending_prompt:
                raise ValueError("BLOCKED_PENDING_CONFIRMATION requires the pending prompt")
            if self.workflow_instance_id is not None or self.draft_action is not None:
                raise ValueError("BLOCKED_PENDING_CONFIRMATION must carry only pending_prompt")
        elif self.status is WorkflowRunStatus.AWAITING_INPUT:
            if not (self.workflow_instance_id and self.pending_prompt):
                raise ValueError("AWAITING_INPUT requires workflow_instance_id and pending_prompt")
            if self.draft_action is not None:
                raise ValueError("AWAITING_INPUT must not carry a draft_action")
        elif (
            self.workflow_instance_id is not None
            or self.draft_action is not None
            or self.pending_prompt is not None
        ):
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
        return cls(
            status=WorkflowRunStatus.NO_GRAPH,
            workflow_key=workflow_key,
            correlation_id=correlation_id,
        )

    @classmethod
    def failed(cls, *, workflow_key: WorkflowKey, correlation_id: str) -> WorkflowRunResult:
        return cls(
            status=WorkflowRunStatus.FAILED,
            workflow_key=workflow_key,
            correlation_id=correlation_id,
        )

    @classmethod
    def blocked_pending_confirmation(
        cls, *, workflow_key: WorkflowKey, correlation_id: str, pending_prompt: str
    ) -> WorkflowRunResult:
        return cls(
            status=WorkflowRunStatus.BLOCKED_PENDING_CONFIRMATION,
            workflow_key=workflow_key,
            correlation_id=correlation_id,
            pending_prompt=pending_prompt,
        )

    @classmethod
    def completed(
        cls,
        *,
        workflow_key: WorkflowKey,
        correlation_id: str,
        pending_prompt: str,
    ) -> WorkflowRunResult:
        return cls(
            status=WorkflowRunStatus.COMPLETED,
            workflow_key=workflow_key,
            correlation_id=correlation_id,
            pending_prompt=pending_prompt,
        )

    @classmethod
    def awaiting_input(
        cls,
        *,
        workflow_key: WorkflowKey,
        correlation_id: str,
        workflow_instance_id: str,
        pending_prompt: str,
    ) -> WorkflowRunResult:
        return cls(
            status=WorkflowRunStatus.AWAITING_INPUT,
            workflow_key=workflow_key,
            correlation_id=correlation_id,
            workflow_instance_id=workflow_instance_id,
            pending_prompt=pending_prompt,
        )


class ResumeAction(str, Enum):
    """The workflow-layer verb for resuming an awaiting workflow. The interaction
    layer maps its InteractionIntent onto this — workflows/ never imports
    interactions/."""

    CONFIRM = "confirm"
    REJECT = "reject"
    CANCEL = "cancel"


class WorkflowResumeStatus(str, Enum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    # The optimistic transition found the row already moved on (duplicate
    # delivery / double reply) — idempotent no-op.
    ALREADY_RESOLVED = "already_resolved"
    # The instance was not in AWAITING_CONFIRMATION.
    NOT_RESUMABLE = "not_resumable"


_RESUME_PHASE: dict[ResumeAction, WorkflowPhase] = {
    ResumeAction.CONFIRM: WorkflowPhase.CONFIRMED,
    ResumeAction.REJECT: WorkflowPhase.REJECTED,
    ResumeAction.CANCEL: WorkflowPhase.CANCELLED,
}


@dataclass(frozen=True, slots=True)
class WorkflowResumeResult:
    """Discriminated resume outcome — only CONFIRMED carries a ConfirmedActionV2."""

    status: WorkflowResumeStatus
    workflow_instance_id: str
    correlation_id: str
    confirmed_action: ConfirmedActionV2 | None = None

    def __post_init__(self) -> None:
        if self.status is WorkflowResumeStatus.CONFIRMED:
            if self.confirmed_action is None:
                raise ValueError("CONFIRMED requires a confirmed_action")
        elif self.confirmed_action is not None:
            raise ValueError(f"{self.status.value} must not carry a confirmed_action")


class WorkflowRuntime:
    """Starts a workflow graph from a PlannerDecision + CanonicalEvent."""

    def __init__(self, registry: WorkflowRegistry, repo: WorkflowInstanceRepository) -> None:
        self._registry = registry
        self._repo = repo

    async def start(
        self, decision: PlannerDecisionV2, event: CanonicalEventV2
    ) -> WorkflowRunResult:
        # Defensive precondition: the runtime is a boundary and enforces this
        # itself rather than relying exclusively on the caller (inbound_journey
        # already only calls start() for START_WORKFLOW, but must not be the
        # only thing standing between a bad decision and a broken graph run).
        if (
            decision.decision_type is not PlannerDecisionType.START_WORKFLOW
            or decision.workflow_key is None
        ):
            raise ValueError(
                "WorkflowRuntime.start() requires a START_WORKFLOW decision with a workflow_key, "
                f"got decision_type={decision.decision_type!r} workflow_key={decision.workflow_key!r}"
            )
        workflow_key = decision.workflow_key

        # Single-active invariant: a user may have at most one AWAITING_CONFIRMATION
        # workflow. If one is pending, block the new one and re-show its prompt
        # rather than piling up ambiguous confirmations. (The partial unique index
        # in Postgres is the hard guarantee; this is the friendly pre-check.)
        # Informational workflows (see _INFORMATIONAL_WORKFLOW_KEYS) are exempt.
        # A pending COLLECTING_FIELDS slot question (Finance Module Slice 1)
        # blocks the same way -- there is no DB-level guarantee for that phase
        # (see workflows/ports.py's get_awaiting_input docstring), so this
        # pre-check is the only thing enforcing it.
        if workflow_key not in _INFORMATIONAL_WORKFLOW_KEYS:
            existing = await self._repo.get_awaiting_confirmation(event.user_id)
            if existing is not None and existing.state.pending_prompt:
                logger.info(
                    "workflow.blocked_pending_confirmation user=%s existing=%s",
                    event.user_id,
                    existing.state.workflow_instance_id,
                )
                return WorkflowRunResult.blocked_pending_confirmation(
                    workflow_key=workflow_key,
                    correlation_id=event.correlation_id,
                    pending_prompt=existing.state.pending_prompt,
                )
            existing_input = await self._repo.get_awaiting_input(event.user_id)
            if existing_input is not None and existing_input.state.pending_prompt:
                logger.info(
                    "workflow.blocked_pending_input user=%s existing=%s",
                    event.user_id,
                    existing_input.state.workflow_instance_id,
                )
                return WorkflowRunResult.blocked_pending_confirmation(
                    workflow_key=workflow_key,
                    correlation_id=event.correlation_id,
                    pending_prompt=existing_input.state.pending_prompt,
                )

        # Look up the graph BEFORE minting any identity: an unmapped key must
        # never generate an orphaned workflow_instance_id.
        graph = self._registry.get_graph(workflow_key)
        if graph is None:
            logger.warning("workflow.no_graph workflow_key=%s", workflow_key.value)
            return WorkflowRunResult.no_graph(
                workflow_key=workflow_key, correlation_id=event.correlation_id
            )

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
            return WorkflowRunResult.failed(
                workflow_key=workflow_key, correlation_id=event.correlation_id
            )

        draft_action: DraftActionV2 | None = result_state.get("draft_action")
        pending_prompt: str | None = result_state.get("pending_prompt")
        awaiting_slot: str | None = result_state.get("awaiting_slot")
        collected_fields = result_state.get("collected_fields", dict(event.fields))

        if awaiting_slot is not None:
            # A node asked a mid-workflow question (e.g. "which account?") --
            # persist as COLLECTING_FIELDS, not yet a draft. collected_fields
            # must come from the graph's result (not event.fields) so the
            # seeded candidate list survives to the next provide_input() call.
            if pending_prompt is None:
                logger.error(
                    "workflow.slot_missing_prompt workflow_key=%s workflow_instance_id=%s",
                    workflow_key.value,
                    workflow_instance_id,
                )
                return WorkflowRunResult.failed(
                    workflow_key=workflow_key, correlation_id=event.correlation_id
                )
            slot_state = WorkflowStateV2(
                workflow_instance_id=workflow_instance_id,
                workflow_key=workflow_key,
                correlation_id=event.correlation_id,
                organization_id=event.organization_id,
                user_id=event.user_id,
                project_id=event.project_id,
                site_id=event.site_id,
                phase=WorkflowPhase.COLLECTING_FIELDS,
                collected_fields=collected_fields,
                awaiting_slot=awaiting_slot,
                pending_prompt=pending_prompt,
            )
            try:
                await self._repo.save(slot_state)
            except Exception:
                logger.exception(
                    "workflow.save_failed workflow_instance_id=%s", workflow_instance_id
                )
                return WorkflowRunResult.failed(
                    workflow_key=workflow_key, correlation_id=event.correlation_id
                )
            return WorkflowRunResult.awaiting_input(
                workflow_key=workflow_key,
                correlation_id=event.correlation_id,
                workflow_instance_id=workflow_instance_id,
                pending_prompt=pending_prompt,
            )

        if pending_prompt is None:
            logger.error(
                "workflow.incomplete_result workflow_key=%s workflow_instance_id=%s",
                workflow_key.value,
                workflow_instance_id,
            )
            return WorkflowRunResult.failed(
                workflow_key=workflow_key, correlation_id=event.correlation_id
            )

        if draft_action is None:
            if workflow_key not in _INFORMATIONAL_WORKFLOW_KEYS:
                logger.error(
                    "workflow.missing_draft_action workflow_key=%s workflow_instance_id=%s",
                    workflow_key.value,
                    workflow_instance_id,
                )
                return WorkflowRunResult.failed(
                    workflow_key=workflow_key, correlation_id=event.correlation_id
                )

            return WorkflowRunResult.completed(
                workflow_key=workflow_key,
                correlation_id=event.correlation_id,
                pending_prompt=pending_prompt,
            )

        state = WorkflowStateV2(
            workflow_instance_id=workflow_instance_id,
            workflow_key=workflow_key,
            correlation_id=event.correlation_id,
            organization_id=event.organization_id,
            user_id=event.user_id,
            project_id=event.project_id,
            site_id=event.site_id,
            phase=WorkflowPhase.AWAITING_CONFIRMATION,
            collected_fields=collected_fields,
            draft_action=draft_action,
            pending_prompt=pending_prompt,
        )

        try:
            await self._repo.save(state)
        except SingleActiveConflict:
            # Lost the check-then-insert race — the DB partial unique index is the
            # real guarantee. Re-fetch to re-show the winning workflow's prompt.
            existing = await self._repo.get_awaiting_confirmation(event.user_id)
            prompt = (
                existing.state.pending_prompt
                if existing is not None and existing.state.pending_prompt
                else "You have a pending confirmation. Please reply YES or NO to it first."
            )
            logger.info("workflow.blocked_pending_confirmation_on_insert user=%s", event.user_id)
            return WorkflowRunResult.blocked_pending_confirmation(
                workflow_key=workflow_key,
                correlation_id=event.correlation_id,
                pending_prompt=prompt,
            )
        except Exception:
            logger.exception("workflow.save_failed workflow_instance_id=%s", workflow_instance_id)
            return WorkflowRunResult.failed(
                workflow_key=workflow_key, correlation_id=event.correlation_id
            )

        return WorkflowRunResult.started(
            workflow_key=workflow_key,
            correlation_id=event.correlation_id,
            workflow_instance_id=workflow_instance_id,
            draft_action=draft_action,
            pending_prompt=pending_prompt,
        )

    async def correct(
        self, loaded: LoadedWorkflowInstance, corrections: list[FieldCorrection]
    ) -> WorkflowRunResult:
        """Applies field corrections and re-runs the workflow graph to generate a new draft."""
        state = loaded.state
        instance_id = state.workflow_instance_id

        if state.phase is not WorkflowPhase.AWAITING_CONFIRMATION:
            return WorkflowRunResult.failed(
                workflow_key=state.workflow_key, correlation_id=state.correlation_id
            )

        new_fields = dict(state.collected_fields)
        for corr in corrections:
            new_fields[corr.field_name] = corr.new_value

        graph = self._registry.get_graph(state.workflow_key)
        if graph is None:
            return WorkflowRunResult.failed(
                workflow_key=state.workflow_key, correlation_id=state.correlation_id
            )

        graph_state: WorkflowGraphState = {
            "workflow_instance_id": instance_id,
            "workflow_key": state.workflow_key.value,
            "correlation_id": state.correlation_id,
            "organization_id": state.organization_id,
            "user_id": state.user_id,
            "project_id": state.project_id,
            "site_id": state.site_id,
            "collected_fields": new_fields,
        }

        try:
            result_state = await graph.ainvoke(graph_state)
        except Exception:
            logger.exception("workflow.correct_failed workflow_instance_id=%s", instance_id)
            return WorkflowRunResult.failed(
                workflow_key=state.workflow_key, correlation_id=state.correlation_id
            )

        draft_action: DraftActionV2 | None = result_state.get("draft_action")
        pending_prompt: str | None = result_state.get("pending_prompt")

        if draft_action is None or pending_prompt is None:
            return WorkflowRunResult.failed(
                workflow_key=state.workflow_key, correlation_id=state.correlation_id
            )

        new_state = state.model_copy(
            update={
                "collected_fields": new_fields,
                "draft_action": draft_action,
                "pending_prompt": pending_prompt,
            }
        )

        applied = await self._repo.transition(instance_id, loaded.version, new_state)
        if not applied:
            # Another event won the race (e.g. duplicate webhook)
            return WorkflowRunResult.failed(
                workflow_key=state.workflow_key, correlation_id=state.correlation_id
            )

        return WorkflowRunResult.started(
            workflow_key=state.workflow_key,
            correlation_id=state.correlation_id,
            workflow_instance_id=instance_id,
            draft_action=draft_action,
            pending_prompt=pending_prompt,
        )

    async def provide_input(
        self, loaded: LoadedWorkflowInstance, answer_text: str
    ) -> WorkflowRunResult:
        """Answers a pending slot question (e.g. "which account?") and re-runs
        the graph. Generalizes correct()'s merge-fields -> re-invoke ->
        transition mechanic: the raw answer text is handed to the graph as
        `_slot_answer_text` and the node that raised the question (e.g.
        expense_capture's resolve_account) is responsible for matching it
        against the candidates it seeded -- this method never matches
        answers itself, only orchestrates the re-run and persistence
        (workflows/ -> no domain-rule matching in the runtime layer).

        Three outcomes: no match (graph re-asks) -> persisted as
        COLLECTING_FIELDS again with the new prompt; resolved -> persisted as
        AWAITING_CONFIRMATION with the built draft; anything else -> FAILED.
        """
        state = loaded.state
        instance_id = state.workflow_instance_id

        if state.phase is not WorkflowPhase.COLLECTING_FIELDS or state.awaiting_slot is None:
            return WorkflowRunResult.failed(
                workflow_key=state.workflow_key, correlation_id=state.correlation_id
            )

        new_fields = dict(state.collected_fields)
        new_fields["_slot_answer_text"] = answer_text

        graph = self._registry.get_graph(state.workflow_key)
        if graph is None:
            return WorkflowRunResult.failed(
                workflow_key=state.workflow_key, correlation_id=state.correlation_id
            )

        graph_state: WorkflowGraphState = {
            "workflow_instance_id": instance_id,
            "workflow_key": state.workflow_key.value,
            "correlation_id": state.correlation_id,
            "organization_id": state.organization_id,
            "user_id": state.user_id,
            "project_id": state.project_id,
            "site_id": state.site_id,
            "collected_fields": new_fields,
            "awaiting_slot": state.awaiting_slot,
        }

        try:
            result_state = await graph.ainvoke(graph_state)
        except Exception:
            logger.exception("workflow.provide_input_failed workflow_instance_id=%s", instance_id)
            return WorkflowRunResult.failed(
                workflow_key=state.workflow_key, correlation_id=state.correlation_id
            )

        draft_action: DraftActionV2 | None = result_state.get("draft_action")
        pending_prompt: str | None = result_state.get("pending_prompt")
        awaiting_slot: str | None = result_state.get("awaiting_slot")
        resolved_fields = result_state.get("collected_fields", new_fields)

        if awaiting_slot is not None:
            # Not matched (or another slot pending) -- ask again.
            if pending_prompt is None:
                return WorkflowRunResult.failed(
                    workflow_key=state.workflow_key, correlation_id=state.correlation_id
                )
            new_state = state.model_copy(
                update={
                    "collected_fields": resolved_fields,
                    "awaiting_slot": awaiting_slot,
                    "pending_prompt": pending_prompt,
                }
            )
            applied = await self._repo.transition(instance_id, loaded.version, new_state)
            if not applied:
                return WorkflowRunResult.failed(
                    workflow_key=state.workflow_key, correlation_id=state.correlation_id
                )
            return WorkflowRunResult.awaiting_input(
                workflow_key=state.workflow_key,
                correlation_id=state.correlation_id,
                workflow_instance_id=instance_id,
                pending_prompt=pending_prompt,
            )

        if draft_action is None or pending_prompt is None:
            return WorkflowRunResult.failed(
                workflow_key=state.workflow_key, correlation_id=state.correlation_id
            )

        new_state = state.model_copy(
            update={
                "collected_fields": resolved_fields,
                "awaiting_slot": None,
                "phase": WorkflowPhase.AWAITING_CONFIRMATION,
                "draft_action": draft_action,
                "pending_prompt": pending_prompt,
            }
        )
        applied = await self._repo.transition(instance_id, loaded.version, new_state)
        if not applied:
            return WorkflowRunResult.failed(
                workflow_key=state.workflow_key, correlation_id=state.correlation_id
            )

        return WorkflowRunResult.started(
            workflow_key=state.workflow_key,
            correlation_id=state.correlation_id,
            workflow_instance_id=instance_id,
            draft_action=draft_action,
            pending_prompt=pending_prompt,
        )

    async def get_awaiting_confirmation(self, user_id: str) -> LoadedWorkflowInstance | None:
        """The user's single awaiting-confirmation instance, or None. Interactions
        talk only to the runtime, never the repo directly."""
        return await self._repo.get_awaiting_confirmation(user_id)

    async def get_awaiting_input(self, user_id: str) -> LoadedWorkflowInstance | None:
        """The user's single COLLECTING_FIELDS instance (pending slot
        question), or None. Interactions talk only to the runtime, never the
        repo directly."""
        return await self._repo.get_awaiting_input(user_id)

    async def resume(
        self, loaded: LoadedWorkflowInstance, action: ResumeAction
    ) -> WorkflowResumeResult:
        """Transition an AWAITING_CONFIRMATION workflow exactly once."""
        state = loaded.state
        instance_id = state.workflow_instance_id

        if state.phase is not WorkflowPhase.AWAITING_CONFIRMATION:
            logger.info(
                "workflow.not_resumable workflow_instance_id=%s phase=%s",
                instance_id,
                state.phase.value,
            )
            return WorkflowResumeResult(
                status=WorkflowResumeStatus.NOT_RESUMABLE,
                workflow_instance_id=instance_id,
                correlation_id=state.correlation_id,
            )

        # Guard before any write: a CONFIRM must be able to produce the handoff.
        # An awaiting instance should always carry a draft, but never half-
        # transition if it somehow doesn't.
        if action is ResumeAction.CONFIRM and state.draft_action is None:
            logger.error("workflow.confirm_without_draft workflow_instance_id=%s", instance_id)
            return WorkflowResumeResult(
                status=WorkflowResumeStatus.NOT_RESUMABLE,
                workflow_instance_id=instance_id,
                correlation_id=state.correlation_id,
            )

        new_phase = _RESUME_PHASE[action]
        new_state = state.model_copy(update={"phase": new_phase})

        applied = await self._repo.transition(instance_id, loaded.version, new_state)
        if not applied:
            # A concurrent transition already moved this instance (duplicate
            # delivery / double reply). Idempotent no-op.
            logger.info("workflow.already_resolved workflow_instance_id=%s", instance_id)
            return WorkflowResumeResult(
                status=WorkflowResumeStatus.ALREADY_RESOLVED,
                workflow_instance_id=instance_id,
                correlation_id=state.correlation_id,
            )

        if action is ResumeAction.CONFIRM:
            confirmed = ConfirmedActionV2(
                confirmed_action_id=new_id("confirmed"),
                workflow_instance_id=instance_id,
                correlation_id=state.correlation_id,
                draft_action=state.draft_action,
                confirmed_by_user_id=state.user_id,
            )
            return WorkflowResumeResult(
                status=WorkflowResumeStatus.CONFIRMED,
                workflow_instance_id=instance_id,
                correlation_id=state.correlation_id,
                confirmed_action=confirmed,
            )

        status = (
            WorkflowResumeStatus.REJECTED
            if action is ResumeAction.REJECT
            else WorkflowResumeStatus.CANCELLED
        )
        return WorkflowResumeResult(
            status=status,
            workflow_instance_id=instance_id,
            correlation_id=state.correlation_id,
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
