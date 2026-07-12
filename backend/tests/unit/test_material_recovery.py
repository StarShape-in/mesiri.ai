"""recover_confirmed_instances — unit tests (fakes only, no DB).

Regression test for Finding #3: recovery must be scoped by workflow_key,
never an unscoped sweep over every CONFIRMED row in the generic
workflow_instances table.
"""

from __future__ import annotations

import pytest

from mesiri.application.materials.fakes import (
    FakeDatabase,
    FakeMaterialExecutionRepository,
    FakeMaterialResolver,
)
from mesiri.application.materials.handlers import ExecuteConfirmedMaterialActionHandler
from mesiri.application.materials.recovery import (
    MATERIAL_WORKFLOW_KEYS,
    recover_confirmed_instances,
)
from mesiri_contracts.application.results.execution_result import ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2
from mesiri_contracts.context.enums import WorkflowPhase

ORG = "11111111-1111-4111-8111-111111111111"
PRJ = "33333333-3333-4333-8333-333333333333"
USR = "22222222-2222-4222-8222-222222222222"


def _confirmed_state(workflow_instance_id: str, workflow_key: WorkflowKey) -> WorkflowStateV2:
    draft = DraftActionV2(
        draft_id=f"draft_{workflow_instance_id}",
        correlation_id=f"cor_{workflow_instance_id}",
        workflow_instance_id=workflow_instance_id,
        action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        fields={"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    return WorkflowStateV2(
        workflow_instance_id=workflow_instance_id,
        workflow_key=workflow_key,
        correlation_id=f"cor_{workflow_instance_id}",
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        phase=WorkflowPhase.CONFIRMED,
        draft_action=draft,
    )


class _FakeLoaded:
    def __init__(self, state: WorkflowStateV2, version: int = 1) -> None:
        self.state = state
        self.version = version


async def test_recovery_only_processes_scoped_workflow_keys(monkeypatch: pytest.MonkeyPatch):
    """Two CONFIRMED rows exist: one Material, one a stand-in for a future
    non-Material workflow. Recovery scoped to Material keys must touch only
    the Material row and leave the other completely untouched."""
    material_state = _confirmed_state("wf_material", WorkflowKey.MATERIAL_RECEIPT)
    other_state = _confirmed_state("wf_other", WorkflowKey.EXPENSE_SUBMIT)

    async def fake_list_confirmed_by_workflow_keys(db, workflow_keys):
        # Simulate the real SQL-level scoping: only rows whose workflow_key is
        # in the requested set are ever returned to the caller.
        all_loaded = [_FakeLoaded(material_state), _FakeLoaded(other_state)]
        return [loaded for loaded in all_loaded if loaded.state.workflow_key.value in workflow_keys]

    monkeypatch.setattr(
        "mesiri.application.materials.recovery.list_confirmed_by_workflow_keys",
        fake_list_confirmed_by_workflow_keys,
    )

    material_repo = FakeMaterialExecutionRepository()
    handler = ExecuteConfirmedMaterialActionHandler(
        db=FakeDatabase(), repo=material_repo, resolver=FakeMaterialResolver()
    )

    results = await recover_confirmed_instances(
        db=FakeDatabase(), handler=handler, workflow_keys=MATERIAL_WORKFLOW_KEYS
    )

    assert len(results) == 1
    assert results[0].status is ExecutionStatus.SUCCEEDED
    # Only the Material row's fields were ever mapped/executed.
    assert len(material_repo.material_rows) == 1
    assert material_repo.material_rows[0]["command"].idempotency_key == "wf_material"


async def test_recovery_replays_confirmed_instance_idempotently(monkeypatch: pytest.MonkeyPatch):
    state = _confirmed_state("wf_replay", WorkflowKey.MATERIAL_RECEIPT)

    async def fake_list_confirmed_by_workflow_keys(db, workflow_keys):
        return [_FakeLoaded(state)]

    monkeypatch.setattr(
        "mesiri.application.materials.recovery.list_confirmed_by_workflow_keys",
        fake_list_confirmed_by_workflow_keys,
    )

    material_repo = FakeMaterialExecutionRepository()
    handler = ExecuteConfirmedMaterialActionHandler(
        db=FakeDatabase(), repo=material_repo, resolver=FakeMaterialResolver()
    )

    first = await recover_confirmed_instances(
        db=FakeDatabase(), handler=handler, workflow_keys=MATERIAL_WORKFLOW_KEYS
    )
    second = await recover_confirmed_instances(
        db=FakeDatabase(), handler=handler, workflow_keys=MATERIAL_WORKFLOW_KEYS
    )

    assert first[0].status is ExecutionStatus.SUCCEEDED
    assert second[0].status is ExecutionStatus.ALREADY_EXECUTED
    assert len(material_repo.material_rows) == 1  # no second insert


async def test_recovery_skips_confirmed_row_without_draft_action(monkeypatch: pytest.MonkeyPatch):
    """Defensive: resume() refuses to confirm without a draft, so this
    shouldn't happen in practice — but recovery must not crash the whole
    sweep if it somehow does."""
    bare_state = WorkflowStateV2(
        workflow_instance_id="wf_bare",
        workflow_key=WorkflowKey.MATERIAL_RECEIPT,
        correlation_id="cor_bare",
        organization_id=ORG,
        user_id=USR,
        phase=WorkflowPhase.CONFIRMED,
        draft_action=None,
    )

    async def fake_list_confirmed_by_workflow_keys(db, workflow_keys):
        return [_FakeLoaded(bare_state)]

    monkeypatch.setattr(
        "mesiri.application.materials.recovery.list_confirmed_by_workflow_keys",
        fake_list_confirmed_by_workflow_keys,
    )

    handler = ExecuteConfirmedMaterialActionHandler(
        db=FakeDatabase(), repo=FakeMaterialExecutionRepository(), resolver=FakeMaterialResolver()
    )
    results = await recover_confirmed_instances(
        db=FakeDatabase(), handler=handler, workflow_keys=MATERIAL_WORKFLOW_KEYS
    )
    assert results == []
