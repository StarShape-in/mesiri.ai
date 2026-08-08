"""CreateProjectHandler — unit tests (fakes only, no DB)."""

from __future__ import annotations

import pytest

from mesiri.application.projects.create_commands import CreateProjectCommand
from mesiri.application.projects.fakes import FakeCreateProjectExecutionRepository, FakeDatabase
from mesiri.application.projects.handlers import CreateProjectHandler
from mesiri_contracts.application.results.execution_result import ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _command(**overrides) -> CreateProjectCommand:
    base = dict(
        idempotency_key="idem_1",
        organization_id=ORG,
        created_by=USR,
        created_by_role="ADMIN",
        name="Skyline Towers",
    )
    base.update(overrides)
    return CreateProjectCommand(**base)


@pytest.mark.asyncio
async def test_valid_create_succeeds_and_persists_one_row():
    repo = FakeCreateProjectExecutionRepository()
    handler = CreateProjectHandler(repo)

    result = await handler.handle(None, _command())

    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.material_row_id is not None
    assert len(repo.project_writes) == 1


@pytest.mark.asyncio
async def test_invalid_command_is_rejected_without_persisting():
    repo = FakeCreateProjectExecutionRepository()
    handler = CreateProjectHandler(repo)

    result = await handler.handle(None, _command(name="  "))

    assert result.status == ExecutionStatus.REJECTED
    assert "project name is required" in result.rejection_reasons
    assert repo.project_writes == []


@pytest.mark.asyncio
async def test_disallowed_role_is_rejected_without_persisting():
    repo = FakeCreateProjectExecutionRepository()
    handler = CreateProjectHandler(repo)

    result = await handler.handle(None, _command(created_by_role="SITE_ENGINEER"))

    assert result.status == ExecutionStatus.REJECTED
    assert "only an admin or project manager can create a project" in result.rejection_reasons
    assert repo.project_writes == []


@pytest.mark.asyncio
async def test_repeated_idempotency_key_replays_without_second_write():
    repo = FakeCreateProjectExecutionRepository()
    handler = CreateProjectHandler(repo)

    first = await handler.handle(None, _command())
    second = await handler.handle(None, _command())

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED
    assert len(repo.project_writes) == 1


def _confirmed(fields: dict) -> ConfirmedActionV2:
    f = {"created_by_role": "ADMIN"}
    f.update(fields)
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.CREATE_PROJECT,
        organization_id=ORG,
        user_id=USR,
        fields=f,
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )


@pytest.mark.asyncio
async def test_handle_confirmed_maps_and_persists_end_to_end():
    repo = FakeCreateProjectExecutionRepository()
    handler = CreateProjectHandler(repo, db=FakeDatabase())

    result = await handler.handle_confirmed(
        _confirmed({"name": "Skyline Towers", "created_by_role": "ADMIN"})
    )

    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.idempotency_key == "wf_1"
    assert len(repo.project_writes) == 1


@pytest.mark.asyncio
async def test_handle_confirmed_replays_on_repeat_workflow_instance_id():
    repo = FakeCreateProjectExecutionRepository()
    handler = CreateProjectHandler(repo, db=FakeDatabase())
    confirmed = _confirmed({"name": "Skyline Towers", "created_by_role": "ADMIN"})

    first = await handler.handle_confirmed(confirmed)
    second = await handler.handle_confirmed(confirmed)

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED
    assert len(repo.project_writes) == 1
