"""WorkflowRuntime.resume — unit tests (fakes only, no LangGraph, no DB)."""

from __future__ import annotations

import pytest

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2
from mesiri_contracts.context.enums import WorkflowPhase
from workflows import (
    ResumeAction,
    WorkflowRegistry,
    WorkflowResumeStatus,
    WorkflowRuntime,
)
from workflows.fakes import FakeWorkflowInstanceRepository

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
WF = "11111111-1111-4111-8111-1111111111aa"


def _awaiting_state(*, phase: WorkflowPhase = WorkflowPhase.AWAITING_CONFIRMATION) -> WorkflowStateV2:
    draft = DraftActionV2(
        draft_id="d1",
        correlation_id="c1",
        workflow_instance_id=WF,
        action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
        organization_id=ORG,
        user_id=USR,
        fields={"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    return WorkflowStateV2(
        workflow_instance_id=WF,
        workflow_key=WorkflowKey.MATERIAL_RECEIPT,
        correlation_id="c1",
        organization_id=ORG,
        user_id=USR,
        phase=phase,
        collected_fields={"material_name": "cement"},
        draft_action=draft,
        pending_prompt="Confirm?",
    )


def _runtime(repo: FakeWorkflowInstanceRepository) -> WorkflowRuntime:
    return WorkflowRuntime(registry=WorkflowRegistry(), repo=repo)


async def test_confirm_produces_confirmed_action_and_bumps_version():
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_state(), version=0)
    runtime = _runtime(repo)

    loaded = await runtime.get_awaiting_confirmation(USR)
    result = await runtime.resume(loaded, ResumeAction.CONFIRM)

    assert result.status is WorkflowResumeStatus.CONFIRMED
    assert result.confirmed_action is not None
    assert result.confirmed_action.confirmed_by_user_id == USR
    assert result.confirmed_action.draft_action.fields == {
        "material_name": "cement",
        "quantity": 20,
        "unit": "bags",
    }
    # persisted transition: phase CONFIRMED, version bumped, no longer awaiting
    stored = repo._rows[WF]
    assert stored[0].phase is WorkflowPhase.CONFIRMED
    assert stored[1] == 1
    assert await runtime.get_awaiting_confirmation(USR) is None


@pytest.mark.parametrize(
    "action,phase",
    [
        (ResumeAction.REJECT, WorkflowPhase.REJECTED),
        (ResumeAction.CANCEL, WorkflowPhase.CANCELLED),
    ],
)
async def test_reject_and_cancel_are_terminal_without_confirmed_action(action, phase):
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_state(), version=0)
    runtime = _runtime(repo)

    loaded = await runtime.get_awaiting_confirmation(USR)
    result = await runtime.resume(loaded, action)

    assert result.status.value == phase.value
    assert result.confirmed_action is None
    assert repo._rows[WF][0].phase is phase


async def test_non_awaiting_instance_is_not_resumable_and_writes_nothing():
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_state(phase=WorkflowPhase.CONFIRMED), version=3)
    runtime = _runtime(repo)

    from workflows.ports import LoadedWorkflowInstance

    loaded = LoadedWorkflowInstance(state=_awaiting_state(phase=WorkflowPhase.CONFIRMED), version=3)
    result = await runtime.resume(loaded, ResumeAction.CONFIRM)

    assert result.status is WorkflowResumeStatus.NOT_RESUMABLE
    assert result.confirmed_action is None
    assert repo._rows[WF][1] == 3  # untouched


async def test_stale_version_is_already_resolved_and_writes_nothing():
    """Duplicate delivery / double reply: the second transition on a stale
    version is an idempotent no-op — exactly-once."""
    repo = FakeWorkflowInstanceRepository()
    repo.seed(_awaiting_state(), version=0)
    runtime = _runtime(repo)

    loaded = await runtime.get_awaiting_confirmation(USR)  # version 0
    first = await runtime.resume(loaded, ResumeAction.CONFIRM)
    assert first.status is WorkflowResumeStatus.CONFIRMED

    # Re-use the same stale loaded (still version 0) — simulates the duplicate.
    second = await runtime.resume(loaded, ResumeAction.CONFIRM)
    assert second.status is WorkflowResumeStatus.ALREADY_RESOLVED
    assert second.confirmed_action is None
    # only one transition applied → version is 1, not 2
    assert repo._rows[WF][1] == 1
