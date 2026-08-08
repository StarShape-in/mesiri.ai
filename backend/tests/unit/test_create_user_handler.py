"""CreateUserHandler — unit tests (fakes only, no DB)."""

from __future__ import annotations

import pytest

from mesiri.application.identity.create_user_commands import CreateUserCommand
from mesiri.application.identity.fakes import FakeCreateUserExecutionRepository, FakeDatabase
from mesiri.application.identity.handlers import CreateUserHandler
from mesiri_contracts.application.results.execution_result import ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _command(**overrides) -> CreateUserCommand:
    base = dict(
        idempotency_key="idem_1",
        organization_id=ORG,
        created_by=USR,
        created_by_role="ADMIN",
        full_name="Rajesh",
        whatsapp_number="919876543210",
        role="SITE_ENGINEER",
    )
    base.update(overrides)
    return CreateUserCommand(**base)


@pytest.mark.asyncio
async def test_valid_command_succeeds_and_persists_one_row():
    repo = FakeCreateUserExecutionRepository()
    handler = CreateUserHandler(repo)

    result = await handler.handle(None, _command())

    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.material_row_id is not None
    assert len(repo.user_writes) == 1


@pytest.mark.asyncio
async def test_disallowed_role_is_rejected_without_persisting():
    repo = FakeCreateUserExecutionRepository()
    handler = CreateUserHandler(repo)

    result = await handler.handle(None, _command(created_by_role="SITE_ENGINEER"))

    assert result.status == ExecutionStatus.REJECTED
    assert "only an admin or project manager can add a new user" in result.rejection_reasons
    assert repo.user_writes == []


@pytest.mark.asyncio
async def test_missing_name_is_rejected():
    repo = FakeCreateUserExecutionRepository()
    handler = CreateUserHandler(repo)

    result = await handler.handle(None, _command(full_name="  "))

    assert result.status == ExecutionStatus.REJECTED
    assert "a name is required to create a user" in result.rejection_reasons
    assert repo.user_writes == []


@pytest.mark.asyncio
async def test_invalid_phone_number_is_rejected():
    repo = FakeCreateUserExecutionRepository()
    handler = CreateUserHandler(repo)

    result = await handler.handle(None, _command(whatsapp_number="123"))

    assert result.status == ExecutionStatus.REJECTED
    assert "a valid WhatsApp number is required to create a user" in result.rejection_reasons
    assert repo.user_writes == []


@pytest.mark.asyncio
async def test_repeated_idempotency_key_replays_without_second_write():
    repo = FakeCreateUserExecutionRepository()
    handler = CreateUserHandler(repo)

    first = await handler.handle(None, _command())
    second = await handler.handle(None, _command())

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED
    assert len(repo.user_writes) == 1


def _confirmed(fields: dict) -> ConfirmedActionV2:
    f = {"created_by_role": "ADMIN", "role": "SITE_ENGINEER"}
    f.update(fields)
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.CREATE_USER,
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
    repo = FakeCreateUserExecutionRepository()
    handler = CreateUserHandler(repo, db=FakeDatabase())

    result = await handler.handle_confirmed(
        _confirmed({"full_name": "Rajesh", "whatsapp_number": "919876543210"})
    )

    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.idempotency_key == "wf_1"
    assert len(repo.user_writes) == 1


@pytest.mark.asyncio
async def test_handle_confirmed_replays_on_repeat_workflow_instance_id():
    repo = FakeCreateUserExecutionRepository()
    handler = CreateUserHandler(repo, db=FakeDatabase())
    confirmed = _confirmed({"full_name": "Rajesh", "whatsapp_number": "919876543210"})

    first = await handler.handle_confirmed(confirmed)
    second = await handler.handle_confirmed(confirmed)

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED
    assert len(repo.user_writes) == 1
