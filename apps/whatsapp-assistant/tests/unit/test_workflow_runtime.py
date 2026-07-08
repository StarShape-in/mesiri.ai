"""WorkflowRuntime + WorkflowRegistry — unit tests (fakes only, no LangGraph, no DB)."""

from __future__ import annotations

import pytest

from mesiri_contracts.assistant.canonical_event import (
    CanonicalEventType,
    IntentCompleteness,
)
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import (
    PlannerDecisionType,
    PlannerPriority,
    WorkflowKey,
)
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from mesiri_contracts.context.enums import WorkflowPhase
from workflows.fakes import FakeWorkflowInstanceRepository
from workflows.runtime import WorkflowRunStatus, WorkflowRuntime


class _FakeGraph:
    """Duck-typed stand-in for a compiled LangGraph graph."""

    def __init__(self, result: dict | None = None, raise_error: bool = False):
        self._result = result
        self._raise = raise_error
        self.invocations = 0

    async def ainvoke(self, state: dict) -> dict:
        self.invocations += 1
        if self._raise:
            raise RuntimeError("boom")
        return {**state, **(self._result or {})}


class _FakeRegistry:
    """Duck-typed stand-in for WorkflowRegistry — no LangGraph import needed."""

    def __init__(self, graphs: dict[WorkflowKey, _FakeGraph]):
        self._graphs = graphs
        self.get_graph_calls: list[WorkflowKey] = []

    def get_graph(self, key: WorkflowKey):
        self.get_graph_calls.append(key)
        return self._graphs.get(key)


ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"


def _decision(
    *, decision_type: PlannerDecisionType, workflow_key: WorkflowKey | None = None
) -> PlannerDecisionV2:
    return PlannerDecisionV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        decision_type=decision_type,
        workflow_key=workflow_key,
        reason=CanonicalEventType.MATERIAL_RECEIPT_REQUESTED,
        priority=PlannerPriority.NORMAL,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=SITE,
    )


def _event(fields: dict | None = None) -> CanonicalEventV2:
    return CanonicalEventV2(
        event_id="evt_1",
        correlation_id="cor_1",
        source_message_id="msg_1",
        event_type=CanonicalEventType.MATERIAL_RECEIPT_REQUESTED,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=SITE,
        fields=fields or {"material_name": "cement", "quantity": 20, "unit": "bags"},
    )


def _draft() -> DraftActionV2:
    return DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="placeholder",
        action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
        organization_id=ORG,
        user_id=USR,
        fields={"material_name": "cement", "quantity": 20, "unit": "bags"},
    )


async def test_start_saves_workflow_state_and_returns_started():
    graph = _FakeGraph(result={"draft_action": _draft(), "pending_prompt": "Confirm?"})
    registry = _FakeRegistry({WorkflowKey.MATERIAL_RECEIPT: graph})
    repo = FakeWorkflowInstanceRepository()
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    decision = _decision(decision_type=PlannerDecisionType.START_WORKFLOW, workflow_key=WorkflowKey.MATERIAL_RECEIPT)
    result = await runtime.start(decision, _event())

    assert result.status is WorkflowRunStatus.STARTED
    assert result.workflow_instance_id is not None
    assert result.draft_action is not None
    assert result.pending_prompt == "Confirm?"

    assert len(repo.saved) == 1
    saved = repo.saved[0]
    assert saved.phase is WorkflowPhase.AWAITING_CONFIRMATION
    assert saved.workflow_instance_id == result.workflow_instance_id
    assert saved.draft_action.fields == {"material_name": "cement", "quantity": 20, "unit": "bags"}


async def test_unmapped_workflow_key_returns_no_graph_and_saves_nothing():
    registry = _FakeRegistry({})  # nothing mapped
    repo = FakeWorkflowInstanceRepository()
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    decision = _decision(decision_type=PlannerDecisionType.START_WORKFLOW, workflow_key=WorkflowKey.MATERIAL_RECEIPT)
    result = await runtime.start(decision, _event())

    assert result.status is WorkflowRunStatus.NO_GRAPH
    assert result.workflow_instance_id is None
    assert repo.saved == []


async def test_graph_exception_returns_failed_and_saves_nothing():
    graph = _FakeGraph(raise_error=True)
    registry = _FakeRegistry({WorkflowKey.MATERIAL_RECEIPT: graph})
    repo = FakeWorkflowInstanceRepository()
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    decision = _decision(decision_type=PlannerDecisionType.START_WORKFLOW, workflow_key=WorkflowKey.MATERIAL_RECEIPT)
    result = await runtime.start(decision, _event())

    assert result.status is WorkflowRunStatus.FAILED
    assert repo.saved == []


async def test_incomplete_graph_result_returns_failed():
    """A graph that doesn't produce both draft_action and pending_prompt must
    not be treated as STARTED."""
    graph = _FakeGraph(result={"draft_action": _draft()})  # missing pending_prompt
    registry = _FakeRegistry({WorkflowKey.MATERIAL_RECEIPT: graph})
    repo = FakeWorkflowInstanceRepository()
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    decision = _decision(decision_type=PlannerDecisionType.START_WORKFLOW, workflow_key=WorkflowKey.MATERIAL_RECEIPT)
    result = await runtime.start(decision, _event())

    assert result.status is WorkflowRunStatus.FAILED
    assert repo.saved == []


@pytest.mark.parametrize(
    "decision_type", [PlannerDecisionType.CLARIFY, PlannerDecisionType.DIRECT_REPLY, PlannerDecisionType.IGNORE]
)
async def test_start_rejects_non_start_workflow_decisions(decision_type: PlannerDecisionType) -> None:
    """The runtime enforces its own precondition rather than trusting the caller."""
    registry = _FakeRegistry({WorkflowKey.MATERIAL_RECEIPT: _FakeGraph()})
    repo = FakeWorkflowInstanceRepository()
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    decision = _decision(decision_type=decision_type, workflow_key=None)
    with pytest.raises(ValueError):
        await runtime.start(decision, _event())

    assert registry.get_graph_calls == []  # never even consults the registry
    assert repo.saved == []


async def test_no_graph_does_not_mint_a_workflow_instance_id():
    """Looking up the graph happens before any identity is generated."""
    registry = _FakeRegistry({})
    repo = FakeWorkflowInstanceRepository()
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    decision = _decision(decision_type=PlannerDecisionType.START_WORKFLOW, workflow_key=WorkflowKey.MATERIAL_RECEIPT)
    result = await runtime.start(decision, _event())

    assert result.workflow_instance_id is None
    assert registry.get_graph_calls == [WorkflowKey.MATERIAL_RECEIPT]


def test_workflow_registry_compiles_once_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real WorkflowRegistry must compile a graph exactly once per key."""
    import workflows.registry as registry_module

    build_calls = {"count": 0}

    def _fake_builder():
        build_calls["count"] += 1
        return object()

    monkeypatch.setitem(registry_module._BUILDERS, WorkflowKey.MATERIAL_RECEIPT, _fake_builder)

    registry = registry_module.WorkflowRegistry()
    first = registry.get_graph(WorkflowKey.MATERIAL_RECEIPT)
    second = registry.get_graph(WorkflowKey.MATERIAL_RECEIPT)

    assert first is second
    assert build_calls["count"] == 1
