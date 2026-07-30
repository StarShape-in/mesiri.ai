"""AddProjectMemberHandler — unit tests (fakes only, no DB)."""

from __future__ import annotations

import pytest

from mesiri.application.projects.add_member_commands import AddProjectMemberCommand
from mesiri.application.projects.fakes import (
    FakeAddProjectMemberExecutionRepository,
    FakeDatabase,
    FakeMemberNameResolver,
)
from mesiri.application.projects.handlers import AddProjectMemberHandler
from mesiri_contracts.application.results.execution_result import ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
PROJ = "33333333-3333-4333-8333-333333333333"
USR = "22222222-2222-4222-8222-222222222222"
RAJESH_ID = "55555555-5555-4555-8555-555555555555"


def _command(**overrides) -> AddProjectMemberCommand:
    base = dict(
        idempotency_key="idem_1",
        organization_id=ORG,
        project_id=PROJ,
        created_by=USR,
        created_by_role="ADMIN",
        member_name="Rajesh",
        role="SITE_ENGINEER",
    )
    base.update(overrides)
    return AddProjectMemberCommand(**base)


@pytest.mark.asyncio
async def test_resolved_name_succeeds_and_persists_one_row():
    repo = FakeAddProjectMemberExecutionRepository()
    resolver = FakeMemberNameResolver({"Rajesh": RAJESH_ID})
    handler = AddProjectMemberHandler(repo, resolver)

    result = await handler.handle(None, _command())

    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.material_row_id == RAJESH_ID
    assert len(repo.member_writes) == 1
    assert repo.member_writes[0]["command"].member_user_id == RAJESH_ID


@pytest.mark.asyncio
async def test_unresolved_name_is_a_hard_rejection():
    repo = FakeAddProjectMemberExecutionRepository()
    resolver = FakeMemberNameResolver({})
    handler = AddProjectMemberHandler(repo, resolver)

    result = await handler.handle(None, _command(member_name="Someone Nonexistent"))

    assert result.status == ExecutionStatus.REJECTED
    assert any("Someone Nonexistent" in r for r in result.rejection_reasons)
    assert repo.member_writes == []


@pytest.mark.asyncio
async def test_disallowed_role_is_rejected_without_persisting():
    repo = FakeAddProjectMemberExecutionRepository()
    resolver = FakeMemberNameResolver({"Rajesh": RAJESH_ID})
    handler = AddProjectMemberHandler(repo, resolver)

    result = await handler.handle(None, _command(created_by_role="SITE_ENGINEER"))

    assert result.status == ExecutionStatus.REJECTED
    assert "only an admin or project manager can add a project member" in result.rejection_reasons
    assert repo.member_writes == []


@pytest.mark.asyncio
async def test_missing_project_is_rejected():
    repo = FakeAddProjectMemberExecutionRepository()
    resolver = FakeMemberNameResolver({"Rajesh": RAJESH_ID})
    handler = AddProjectMemberHandler(repo, resolver)

    result = await handler.handle(None, _command(project_id=""))

    assert result.status == ExecutionStatus.REJECTED
    assert "a project is required to add a member" in result.rejection_reasons
    assert repo.member_writes == []


@pytest.mark.asyncio
async def test_repeated_idempotency_key_replays_without_second_write():
    repo = FakeAddProjectMemberExecutionRepository()
    resolver = FakeMemberNameResolver({"Rajesh": RAJESH_ID})
    handler = AddProjectMemberHandler(repo, resolver)

    first = await handler.handle(None, _command())
    second = await handler.handle(None, _command())

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED
    assert len(repo.member_writes) == 1


def _confirmed(fields: dict) -> ConfirmedActionV2:
    f = {"created_by_role": "ADMIN", "role": "SITE_ENGINEER"}
    f.update(fields)
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.ADD_PROJECT_MEMBER,
        organization_id=ORG,
        user_id=USR,
        project_id=PROJ,
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
    repo = FakeAddProjectMemberExecutionRepository()
    resolver = FakeMemberNameResolver({"Rajesh": RAJESH_ID})
    handler = AddProjectMemberHandler(repo, resolver, db=FakeDatabase())

    result = await handler.handle_confirmed(_confirmed({"member_name": "Rajesh"}))

    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.idempotency_key == "wf_1"
    assert len(repo.member_writes) == 1


@pytest.mark.asyncio
async def test_handle_confirmed_replays_on_repeat_workflow_instance_id():
    repo = FakeAddProjectMemberExecutionRepository()
    resolver = FakeMemberNameResolver({"Rajesh": RAJESH_ID})
    handler = AddProjectMemberHandler(repo, resolver, db=FakeDatabase())
    confirmed = _confirmed({"member_name": "Rajesh"})

    first = await handler.handle_confirmed(confirmed)
    second = await handler.handle_confirmed(confirmed)

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED
    assert len(repo.member_writes) == 1
