"""ProjectingExecutionDispatcher — unit tests (fakes only, no DB, no context layer)."""

from __future__ import annotations

import uuid

import pytest

from interactions.projecting_dispatcher import ProjectingExecutionDispatcher
from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


class _FakeInnerDispatcher:
    def __init__(self, result: ExecutionResult) -> None:
        self._result = result
        self.dispatch_calls = 0

    async def dispatch(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        self.dispatch_calls += 1
        return self._result


def _confirmed() -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.CREATE_PROJECT,
        organization_id=ORG,
        user_id=USR,
        fields={"name": "Skyline Towers"},
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )


@pytest.mark.asyncio
async def test_succeeded_result_triggers_projection_with_the_new_row_id(monkeypatch):
    row_id = str(uuid.uuid4())
    calls: list[tuple[str, uuid.UUID]] = []

    async def _fake_project_entity(entity_type, entity_id):
        calls.append((entity_type, entity_id))

    monkeypatch.setattr(
        "interactions.projecting_dispatcher.project_entity", _fake_project_entity
    )
    inner = _FakeInnerDispatcher(
        ExecutionResult(status=ExecutionStatus.SUCCEEDED, idempotency_key="wf_1", material_row_id=row_id)
    )
    dispatcher = ProjectingExecutionDispatcher(inner, "project")

    result = await dispatcher.dispatch(_confirmed())

    assert result.status == ExecutionStatus.SUCCEEDED
    assert calls == [("project", uuid.UUID(row_id))]


@pytest.mark.asyncio
async def test_rejected_result_never_triggers_projection(monkeypatch):
    calls: list[tuple[str, uuid.UUID]] = []

    async def _fake_project_entity(entity_type, entity_id):
        calls.append((entity_type, entity_id))

    monkeypatch.setattr(
        "interactions.projecting_dispatcher.project_entity", _fake_project_entity
    )
    inner = _FakeInnerDispatcher(
        ExecutionResult(status=ExecutionStatus.REJECTED, idempotency_key="wf_1", rejection_reasons=["x"])
    )
    dispatcher = ProjectingExecutionDispatcher(inner, "project")

    result = await dispatcher.dispatch(_confirmed())

    assert result.status == ExecutionStatus.REJECTED
    assert calls == []


@pytest.mark.asyncio
async def test_projection_failure_does_not_turn_a_success_into_a_failure(monkeypatch):
    async def _raising_project_entity(entity_type, entity_id):
        raise RuntimeError("context db unreachable")

    monkeypatch.setattr(
        "interactions.projecting_dispatcher.project_entity", _raising_project_entity
    )
    inner = _FakeInnerDispatcher(
        ExecutionResult(
            status=ExecutionStatus.SUCCEEDED, idempotency_key="wf_1", material_row_id=str(uuid.uuid4())
        )
    )
    dispatcher = ProjectingExecutionDispatcher(inner, "site")

    result = await dispatcher.dispatch(_confirmed())

    assert result.status == ExecutionStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_dispatch_delegates_exactly_once_to_inner(monkeypatch):
    async def _fake_project_entity(entity_type, entity_id):
        return None

    monkeypatch.setattr(
        "interactions.projecting_dispatcher.project_entity", _fake_project_entity
    )
    inner = _FakeInnerDispatcher(
        ExecutionResult(
            status=ExecutionStatus.SUCCEEDED, idempotency_key="wf_1", material_row_id=str(uuid.uuid4())
        )
    )
    dispatcher = ProjectingExecutionDispatcher(inner, "project")

    await dispatcher.dispatch(_confirmed())

    assert inner.dispatch_calls == 1
