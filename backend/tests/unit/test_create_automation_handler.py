"""CreateAutomationHandler — unit tests (fakes only, no DB)."""

from __future__ import annotations

import pytest

from mesiri.application.automations.create_commands import CreateAutomationCommand
from mesiri.application.automations.fakes import (
    FakeAudienceNameResolver,
    FakeCreateAutomationExecutionRepository,
    FakeDatabase,
)
from mesiri.application.automations.handlers import CreateAutomationHandler
from mesiri_contracts.application.results.execution_result import ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
ILAN_ID = "55555555-5555-4555-8555-555555555555"


def _command(**overrides) -> CreateAutomationCommand:
    base = dict(
        idempotency_key="idem_1",
        organization_id=ORG,
        created_by=USR,
        created_by_role="ADMIN",
        action="REMINDER",
        audience="SELF",
        message="please submit your DPR",
        time_of_day="17:00",
    )
    base.update(overrides)
    return CreateAutomationCommand(**base)


@pytest.mark.asyncio
async def test_valid_self_digest_succeeds_and_persists_one_row():
    repo = FakeCreateAutomationExecutionRepository()
    handler = CreateAutomationHandler(repo, FakeAudienceNameResolver())

    result = await handler.handle(None, _command())

    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.material_row_id is not None
    assert len(repo.automation_writes) == 1


@pytest.mark.asyncio
async def test_invalid_command_is_rejected_without_persisting():
    repo = FakeCreateAutomationExecutionRepository()
    handler = CreateAutomationHandler(repo, FakeAudienceNameResolver())

    result = await handler.handle(None, _command(action="REMINDER", message="  "))

    assert result.status == ExecutionStatus.REJECTED
    assert "message is required when action is REMINDER" in result.rejection_reasons
    assert repo.automation_writes == []


@pytest.mark.asyncio
async def test_disallowed_role_targeting_others_is_rejected():
    repo = FakeCreateAutomationExecutionRepository()
    handler = CreateAutomationHandler(repo, FakeAudienceNameResolver())

    result = await handler.handle(
        None,
        _command(
            created_by_role="SITE_ENGINEER",
            audience="ROLE",
            audience_role="SITE_ENGINEER",
            message=None,
        ),
    )

    assert result.status == ExecutionStatus.REJECTED
    assert (
        "only an admin or project manager can target an automation at other people"
        in result.rejection_reasons
    )
    assert repo.automation_writes == []


@pytest.mark.asyncio
async def test_audience_names_resolve_to_user_ids_before_persist():
    repo = FakeCreateAutomationExecutionRepository()
    resolver = FakeAudienceNameResolver({"Ilan": ILAN_ID})
    handler = CreateAutomationHandler(repo, resolver)

    result = await handler.handle(
        None,
        _command(
            audience="USERS",
            audience_names=["Ilan"],
            message="please submit your DPR",
        ),
    )

    assert result.status == ExecutionStatus.SUCCEEDED
    assert len(repo.automation_writes) == 1
    persisted_cmd = repo.automation_writes[0]["command"]
    assert persisted_cmd.audience_user_ids == [ILAN_ID]


@pytest.mark.asyncio
async def test_unresolved_audience_name_is_a_hard_rejection():
    """An unrecognised name is never silently dropped -- proceeding with a
    partially-resolved audience would message some people and silently skip
    whoever was misspelled, exactly the silent-default this must avoid."""
    repo = FakeCreateAutomationExecutionRepository()
    resolver = FakeAudienceNameResolver({"Ilan": ILAN_ID})
    handler = CreateAutomationHandler(repo, resolver)

    result = await handler.handle(
        None,
        _command(
            audience="USERS",
            audience_names=["Ilan", "Someone Nonexistent"],
            message="please submit your DPR",
        ),
    )

    assert result.status == ExecutionStatus.REJECTED
    assert any("Someone Nonexistent" in r for r in result.rejection_reasons)
    assert repo.automation_writes == []


@pytest.mark.asyncio
async def test_repeated_idempotency_key_replays_without_second_write():
    repo = FakeCreateAutomationExecutionRepository()
    handler = CreateAutomationHandler(repo, FakeAudienceNameResolver())

    first = await handler.handle(None, _command())
    second = await handler.handle(None, _command())

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED
    assert len(repo.automation_writes) == 1


def _confirmed(fields: dict) -> ConfirmedActionV2:
    f = {"created_by_role": "ADMIN"}
    f.update(fields)
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.CREATE_AUTOMATION,
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
    repo = FakeCreateAutomationExecutionRepository()
    handler = CreateAutomationHandler(repo, FakeAudienceNameResolver(), db=FakeDatabase())

    result = await handler.handle_confirmed(
        _confirmed(
            {"action": "REMINDER", "audience": "SELF", "message": "hi", "time_of_day": "17:00"}
        )
    )

    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.idempotency_key == "wf_1"
    assert len(repo.automation_writes) == 1


@pytest.mark.asyncio
async def test_handle_confirmed_replays_on_repeat_workflow_instance_id():
    repo = FakeCreateAutomationExecutionRepository()
    handler = CreateAutomationHandler(repo, FakeAudienceNameResolver(), db=FakeDatabase())
    confirmed = _confirmed(
        {"action": "REMINDER", "audience": "SELF", "message": "hi", "time_of_day": "17:00"}
    )

    first = await handler.handle_confirmed(confirmed)
    second = await handler.handle_confirmed(confirmed)

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED
    assert len(repo.automation_writes) == 1
