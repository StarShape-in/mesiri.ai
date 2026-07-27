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
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2
from mesiri_contracts.context.enums import WorkflowPhase
from workflows.fakes import FakeWorkflowInstanceRepository
from workflows.ports import LoadedWorkflowInstance
from workflows.runtime import WorkflowRunResult, WorkflowRunStatus, WorkflowRuntime
from workflows.slots import SlotCandidate


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

    decision = _decision(
        decision_type=PlannerDecisionType.START_WORKFLOW, workflow_key=WorkflowKey.MATERIAL_RECEIPT
    )
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

    decision = _decision(
        decision_type=PlannerDecisionType.START_WORKFLOW, workflow_key=WorkflowKey.MATERIAL_RECEIPT
    )
    result = await runtime.start(decision, _event())

    assert result.status is WorkflowRunStatus.NO_GRAPH
    assert result.workflow_instance_id is None
    assert repo.saved == []


async def test_graph_exception_returns_failed_and_saves_nothing():
    graph = _FakeGraph(raise_error=True)
    registry = _FakeRegistry({WorkflowKey.MATERIAL_RECEIPT: graph})
    repo = FakeWorkflowInstanceRepository()
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    decision = _decision(
        decision_type=PlannerDecisionType.START_WORKFLOW, workflow_key=WorkflowKey.MATERIAL_RECEIPT
    )
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

    decision = _decision(
        decision_type=PlannerDecisionType.START_WORKFLOW, workflow_key=WorkflowKey.MATERIAL_RECEIPT
    )
    result = await runtime.start(decision, _event())

    assert result.status is WorkflowRunStatus.FAILED
    assert repo.saved == []


@pytest.mark.parametrize(
    "decision_type",
    [PlannerDecisionType.CLARIFY, PlannerDecisionType.DIRECT_REPLY, PlannerDecisionType.IGNORE],
)
async def test_start_rejects_non_start_workflow_decisions(
    decision_type: PlannerDecisionType,
) -> None:
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

    decision = _decision(
        decision_type=PlannerDecisionType.START_WORKFLOW, workflow_key=WorkflowKey.MATERIAL_RECEIPT
    )
    result = await runtime.start(decision, _event())

    assert result.workflow_instance_id is None
    assert registry.get_graph_calls == [WorkflowKey.MATERIAL_RECEIPT]


async def test_start_with_awaiting_slot_persists_collecting_fields_and_returns_awaiting_input():
    """Finance Module Slice 1: a node that asks "which one?" must persist as
    COLLECTING_FIELDS, not AWAITING_CONFIRMATION, and carry no draft yet."""
    graph = _FakeGraph(
        result={
            "awaiting_slot": "account_id",
            "pending_prompt": "Which account?",
            "collected_fields": {"amount": 250, "account_candidates": [{"id": "a1", "name": "Cash"}]},
        }
    )
    registry = _FakeRegistry({WorkflowKey.EXPENSE_SUBMIT: graph})
    repo = FakeWorkflowInstanceRepository()
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    decision = _decision(
        decision_type=PlannerDecisionType.START_WORKFLOW, workflow_key=WorkflowKey.EXPENSE_SUBMIT
    )
    result = await runtime.start(decision, _event({"amount": 250}))

    assert result.status is WorkflowRunStatus.AWAITING_INPUT
    assert result.workflow_instance_id is not None
    assert result.draft_action is None
    assert result.pending_prompt == "Which account?"

    assert len(repo.saved) == 1
    saved = repo.saved[0]
    assert saved.phase is WorkflowPhase.COLLECTING_FIELDS
    assert saved.awaiting_slot == "account_id"
    assert saved.collected_fields["account_candidates"] == [{"id": "a1", "name": "Cash"}]


async def test_start_with_awaiting_slot_options_carries_them_onto_the_result():
    """A node that supplies `awaiting_slot_options` (workflows/slots.py's
    slot_options helper) must have them surface on WorkflowRunResult.slot_options
    so the send side can offer a real WhatsApp interactive list."""
    graph = _FakeGraph(
        result={
            "awaiting_slot": "account_id",
            "pending_prompt": "Which account?",
            "awaiting_slot_options": [
                {"value": "a1", "label": "Cash"},
                {"value": "a2", "label": "Bank"},
            ],
            "collected_fields": {"amount": 250},
        }
    )
    registry = _FakeRegistry({WorkflowKey.EXPENSE_SUBMIT: graph})
    repo = FakeWorkflowInstanceRepository()
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    decision = _decision(
        decision_type=PlannerDecisionType.START_WORKFLOW, workflow_key=WorkflowKey.EXPENSE_SUBMIT
    )
    result = await runtime.start(decision, _event({"amount": 250}))

    assert result.slot_options is not None
    assert [(o.value, o.label) for o in result.slot_options] == [("a1", "Cash"), ("a2", "Bank")]


async def test_start_without_awaiting_slot_options_leaves_it_none():
    """A node that hasn't been updated to supply options yet must not crash --
    slot_options is optional, plain text is the fallback."""
    graph = _FakeGraph(
        result={
            "awaiting_slot": "account_id",
            "pending_prompt": "Which account?",
            "collected_fields": {"amount": 250},
        }
    )
    registry = _FakeRegistry({WorkflowKey.EXPENSE_SUBMIT: graph})
    repo = FakeWorkflowInstanceRepository()
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    decision = _decision(
        decision_type=PlannerDecisionType.START_WORKFLOW, workflow_key=WorkflowKey.EXPENSE_SUBMIT
    )
    result = await runtime.start(decision, _event({"amount": 250}))

    assert result.slot_options is None


def test_slot_options_on_a_non_awaiting_input_status_is_rejected():
    """slot_options only ever means something alongside a live slot
    question -- carrying it on e.g. a COMPLETED result would be a bug."""
    with pytest.raises(ValueError, match="must not carry slot_options"):
        WorkflowRunResult(
            status=WorkflowRunStatus.COMPLETED,
            workflow_key=WorkflowKey.WHO_AM_I,
            correlation_id="cor_1",
            pending_prompt="Here is your profile...",
            slot_options=(SlotCandidate(value="a1", label="Cash"),),
        )


async def test_start_blocks_when_user_already_has_a_pending_slot_question():
    repo = FakeWorkflowInstanceRepository()
    existing = WorkflowStateV2(
        workflow_instance_id="wf_existing",
        workflow_key=WorkflowKey.EXPENSE_SUBMIT,
        correlation_id="cor_0",
        organization_id=ORG,
        user_id=USR,
        phase=WorkflowPhase.COLLECTING_FIELDS,
        awaiting_slot="account_id",
        pending_prompt="Which account? (existing)",
    )
    repo.seed(existing)
    registry = _FakeRegistry({WorkflowKey.EXPENSE_SUBMIT: _FakeGraph()})
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    decision = _decision(
        decision_type=PlannerDecisionType.START_WORKFLOW, workflow_key=WorkflowKey.EXPENSE_SUBMIT
    )
    result = await runtime.start(decision, _event())

    assert result.status is WorkflowRunStatus.BLOCKED_PENDING_CONFIRMATION
    assert result.pending_prompt == "Which account? (existing)"
    # The new workflow must never have been invoked at all.
    assert len(repo.saved) == 1  # only the seeded existing row


async def test_provide_input_resolves_slot_and_transitions_to_awaiting_confirmation():
    repo = FakeWorkflowInstanceRepository()
    collecting = WorkflowStateV2(
        workflow_instance_id="wf_1",
        workflow_key=WorkflowKey.EXPENSE_SUBMIT,
        correlation_id="cor_1",
        organization_id=ORG,
        user_id=USR,
        phase=WorkflowPhase.COLLECTING_FIELDS,
        collected_fields={"amount": 250, "account_candidates": [{"id": "a1", "name": "Cash"}]},
        awaiting_slot="account_id",
        pending_prompt="Which account?",
    )
    repo.seed(collecting, version=0)
    loaded = LoadedWorkflowInstance(state=collecting, version=0)

    graph = _FakeGraph(
        result={
            "draft_action": _draft(),
            "pending_prompt": "Confirm?",
            "awaiting_slot": None,
            "collected_fields": {"amount": 250, "account_id": "a1"},
        }
    )
    registry = _FakeRegistry({WorkflowKey.EXPENSE_SUBMIT: graph})
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    result = await runtime.provide_input(loaded, "1")

    assert result.status is WorkflowRunStatus.STARTED
    assert result.pending_prompt == "Confirm?"
    saved_state, _ = repo._rows["wf_1"]  # noqa: SLF001 — test introspection
    assert saved_state.phase is WorkflowPhase.AWAITING_CONFIRMATION
    assert saved_state.awaiting_slot is None
    assert saved_state.collected_fields["account_id"] == "a1"


async def test_provide_input_no_match_reasks_and_stays_collecting_fields():
    repo = FakeWorkflowInstanceRepository()
    collecting = WorkflowStateV2(
        workflow_instance_id="wf_1",
        workflow_key=WorkflowKey.EXPENSE_SUBMIT,
        correlation_id="cor_1",
        organization_id=ORG,
        user_id=USR,
        phase=WorkflowPhase.COLLECTING_FIELDS,
        collected_fields={"amount": 250, "account_candidates": [{"id": "a1", "name": "Cash"}]},
        awaiting_slot="account_id",
        pending_prompt="Which account?",
    )
    repo.seed(collecting, version=0)
    loaded = LoadedWorkflowInstance(state=collecting, version=0)

    graph = _FakeGraph(
        result={
            "awaiting_slot": "account_id",
            "pending_prompt": "Sorry, I didn't catch that. Which account?",
            "collected_fields": {"amount": 250, "account_candidates": [{"id": "a1", "name": "Cash"}]},
        }
    )
    registry = _FakeRegistry({WorkflowKey.EXPENSE_SUBMIT: graph})
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    result = await runtime.provide_input(loaded, "purple monkey dishwasher")

    assert result.status is WorkflowRunStatus.AWAITING_INPUT
    assert result.draft_action is None
    saved_state, _ = repo._rows["wf_1"]  # noqa: SLF001 — test introspection
    assert saved_state.phase is WorkflowPhase.COLLECTING_FIELDS
    assert saved_state.awaiting_slot == "account_id"


async def test_provide_input_rejects_when_phase_is_not_collecting_fields():
    repo = FakeWorkflowInstanceRepository()
    confirming = WorkflowStateV2(
        workflow_instance_id="wf_1",
        workflow_key=WorkflowKey.EXPENSE_SUBMIT,
        correlation_id="cor_1",
        organization_id=ORG,
        user_id=USR,
        phase=WorkflowPhase.AWAITING_CONFIRMATION,
        draft_action=_draft(),
        pending_prompt="Confirm?",
    )
    loaded = LoadedWorkflowInstance(state=confirming, version=0)
    registry = _FakeRegistry({WorkflowKey.EXPENSE_SUBMIT: _FakeGraph()})
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    result = await runtime.provide_input(loaded, "1")

    assert result.status is WorkflowRunStatus.FAILED


async def test_informational_workflow_completes_without_confirmation():
    """Finance Module Slice 2: a query workflow (no draft_action, ever) must
    complete straight away -- never persisted, never AWAITING_CONFIRMATION,
    and exempt from the single-active pending-confirmation block."""
    graph = _FakeGraph(result={"pending_prompt": "💰 Site Cash: ₹3800"})
    registry = _FakeRegistry({WorkflowKey.ACCOUNT_BALANCE_QUERY: graph})
    repo = FakeWorkflowInstanceRepository()
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    decision = _decision(
        decision_type=PlannerDecisionType.START_WORKFLOW,
        workflow_key=WorkflowKey.ACCOUNT_BALANCE_QUERY,
    )
    result = await runtime.start(decision, _event())

    assert result.status is WorkflowRunStatus.COMPLETED
    assert result.pending_prompt == "💰 Site Cash: ₹3800"
    assert result.workflow_instance_id is None
    assert repo.saved == []


async def test_informational_workflow_is_exempt_from_pending_confirmation_block():
    repo = FakeWorkflowInstanceRepository()
    existing = WorkflowStateV2(
        workflow_instance_id="wf_existing",
        workflow_key=WorkflowKey.MATERIAL_RECEIPT,
        correlation_id="cor_0",
        organization_id=ORG,
        user_id=USR,
        phase=WorkflowPhase.AWAITING_CONFIRMATION,
        draft_action=_draft(),
        pending_prompt="Confirm the pending receipt?",
    )
    repo.seed(existing)
    graph = _FakeGraph(result={"pending_prompt": "💰 Site Cash: ₹3800"})
    registry = _FakeRegistry({WorkflowKey.ACCOUNT_BALANCE_QUERY: graph})
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    decision = _decision(
        decision_type=PlannerDecisionType.START_WORKFLOW,
        workflow_key=WorkflowKey.ACCOUNT_BALANCE_QUERY,
    )
    result = await runtime.start(decision, _event())

    assert result.status is WorkflowRunStatus.COMPLETED


async def test_reverse_completes_without_a_draft_when_nothing_to_reverse():
    """Finance Module Slice 7: WorkflowKey.REVERSE is a *mixed* case -- it
    can complete with no draft_action (nothing found to reverse), unlike a
    pure query workflow, but this must not accidentally exempt it from the
    single-active pending-confirmation gate (see the next test)."""
    graph = _FakeGraph(result={"pending_prompt": "You have no confirmed expenses to reverse."})
    registry = _FakeRegistry({WorkflowKey.REVERSE: graph})
    repo = FakeWorkflowInstanceRepository()
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    decision = _decision(decision_type=PlannerDecisionType.START_WORKFLOW, workflow_key=WorkflowKey.REVERSE)
    result = await runtime.start(decision, _event())

    assert result.status is WorkflowRunStatus.COMPLETED
    assert result.pending_prompt == "You have no confirmed expenses to reverse."
    assert repo.saved == []


async def test_reverse_still_blocks_when_a_confirmation_is_already_pending():
    """Real regression: WorkflowKey.REVERSE being allowed to complete
    without a draft must not make it exempt from the single-active
    pending-confirmation block the way a true informational workflow is --
    a user must not be able to start a reversal while an unrelated
    confirmation (or slot question) is already pending. The graph here
    would happily produce a "nothing to reverse" reply if invoked; proving
    it's never invoked is the point."""
    repo = FakeWorkflowInstanceRepository()
    existing = WorkflowStateV2(
        workflow_instance_id="wf_existing",
        workflow_key=WorkflowKey.TRANSFER,
        correlation_id="cor_0",
        organization_id=ORG,
        user_id=USR,
        phase=WorkflowPhase.AWAITING_CONFIRMATION,
        draft_action=_draft(),
        pending_prompt="Confirm the pending transfer?",
    )
    repo.seed(existing)
    graph = _FakeGraph(result={"pending_prompt": "You have no confirmed expenses to reverse."})
    registry = _FakeRegistry({WorkflowKey.REVERSE: graph})
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    decision = _decision(decision_type=PlannerDecisionType.START_WORKFLOW, workflow_key=WorkflowKey.REVERSE)
    result = await runtime.start(decision, _event())

    assert result.status is WorkflowRunStatus.BLOCKED_PENDING_CONFIRMATION
    assert result.pending_prompt == "Confirm the pending transfer?"
    assert graph.invocations == 0


async def test_expense_submit_completes_without_a_draft_when_duplicate_declined():
    """Finance Module Slice 8: expense_capture's check_duplicate node can
    also complete with no draft_action (the user said "no" to "record
    anyway?")."""
    graph = _FakeGraph(result={"pending_prompt": "Ok, I won't record that expense."})
    registry = _FakeRegistry({WorkflowKey.EXPENSE_SUBMIT: graph})
    repo = FakeWorkflowInstanceRepository()
    runtime = WorkflowRuntime(registry=registry, repo=repo)

    decision = _decision(
        decision_type=PlannerDecisionType.START_WORKFLOW, workflow_key=WorkflowKey.EXPENSE_SUBMIT
    )
    result = await runtime.start(decision, _event())

    assert result.status is WorkflowRunStatus.COMPLETED
    assert result.pending_prompt == "Ok, I won't record that expense."
    assert repo.saved == []


def test_workflow_registry_compiles_once_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real WorkflowRegistry must compile a graph exactly once per key."""
    import workflows.registry as registry_module

    build_calls = {"count": 0}

    def _fake_builder():
        build_calls["count"] += 1
        return object()

    monkeypatch.setitem(
        registry_module._DEFINITIONS,
        WorkflowKey.MATERIAL_RECEIPT,
        registry_module.WorkflowDefinition(
            key=WorkflowKey.MATERIAL_RECEIPT,
            builder=_fake_builder,
            category=registry_module.WorkflowCategory.MATERIAL,
        ),
    )

    registry = registry_module.WorkflowRegistry()
    first = registry.get_graph(WorkflowKey.MATERIAL_RECEIPT)
    second = registry.get_graph(WorkflowKey.MATERIAL_RECEIPT)

    assert first is second
    assert build_calls["count"] == 1


def test_informational_and_no_draft_keys_are_pinned() -> None:
    """Pins which keys are informational / may complete without a draft.

    Regression guard for the WorkflowDefinition migration: runtime.py used to
    hardcode these as two frozensets; it now reads WorkflowDefinition via
    is_informational()/allows_completion_without_draft(). This test protects
    against either set silently drifting when a workflow is added or a
    definition is edited."""
    from workflows.registry import (
        allows_completion_without_draft,
        is_informational,
        iter_definitions,
    )

    informational = {d.key for d in iter_definitions() if is_informational(d.key)}
    no_draft = {d.key for d in iter_definitions() if allows_completion_without_draft(d.key)}

    assert informational == {
        WorkflowKey.WHO_AM_I,
        WorkflowKey.MATERIAL_INVENTORY_QUERY,
        WorkflowKey.ACCOUNT_BALANCE_QUERY,
        WorkflowKey.EXPENSE_QUERY,
        # Labour's read side: "how many workers today?" answers and stops.
        # Being informational is what stops an unrelated pending confirmation
        # blocking a question that changes nothing.
        WorkflowKey.LABOUR_QUERY,
        # Writes the register directly inside the node -- the user's numbered
        # reply IS the confirmation, so it must never be blocked by (or block)
        # an unrelated pending confirmation. See worker_promotion/graph.py.
        WorkflowKey.WORKER_PROMOTION,
        # #17 Search / Ask Mesiri's read side: "what did I log today?" /
        # "any open issues?" answers and stops, same reasoning as LABOUR_QUERY.
        WorkflowKey.ACTIVITY_QUERY,
        # #16 Daily Report Generation's chat trigger: "send me today's DPR"
        # answers with status text and stops -- the PDF itself (if ready) is
        # delivered as a side-channel document send, never a draft/confirm.
        WorkflowKey.DPR_REQUEST,
    }
    assert no_draft == informational | {
        WorkflowKey.REVERSE,
        WorkflowKey.EXPENSE_SUBMIT,
        WorkflowKey.ACCOUNT_ADMIN,
        # Same reasoning as REVERSE: the target activity is resolved by
        # seeding (runtime/inbound_journey.py's _seed_open_activity), never
        # stated by the user, so a bare narrative ("finished") is a complete,
        # actionable continuation with no draft fields to fill.
        WorkflowKey.ACTIVITY_CONTINUATION,
    }


def test_every_registered_workflow_has_a_category() -> None:
    """Category is metadata-only today, so nothing else would catch a gap."""
    from workflows.registry import WorkflowCategory, iter_definitions

    for definition in iter_definitions():
        assert isinstance(definition.category, WorkflowCategory), definition.key
