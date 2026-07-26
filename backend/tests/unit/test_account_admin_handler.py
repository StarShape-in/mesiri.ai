"""ManageMoneyAccountHandler — unit tests (fakes only, no DB)."""

from __future__ import annotations

import pytest

from mesiri.application.finance.commands import ManageMoneyAccountCommand
from mesiri.application.finance.fakes import (
    FakeAccountAdminExecutionRepository,
    FakeAccountLookupResolver,
    FakeDatabase,
    RejectingAccountLookupResolver,
)
from mesiri.application.finance.handlers import ManageMoneyAccountHandler
from mesiri_contracts.application.results.execution_result import ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _command(**overrides) -> ManageMoneyAccountCommand:
    base = dict(
        idempotency_key="idem_1",
        organization_id=ORG,
        created_by=USR,
        created_by_role="ADMIN",
        action="create",
        name="Site Cash",
    )
    base.update(overrides)
    return ManageMoneyAccountCommand(**base)


@pytest.mark.asyncio
async def test_valid_create_succeeds_and_persists_one_row():
    repo = FakeAccountAdminExecutionRepository()
    handler = ManageMoneyAccountHandler(repo)

    result = await handler.handle(None, _command())

    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.material_row_id is not None
    assert len(repo.account_writes) == 1


@pytest.mark.asyncio
async def test_invalid_command_is_rejected_without_persisting():
    repo = FakeAccountAdminExecutionRepository()
    handler = ManageMoneyAccountHandler(repo)

    result = await handler.handle(None, _command(name=None))

    assert result.status == ExecutionStatus.REJECTED
    assert "account name is required" in result.rejection_reasons
    assert repo.account_writes == []


@pytest.mark.asyncio
async def test_repeated_idempotency_key_replays_without_second_write():
    repo = FakeAccountAdminExecutionRepository()
    handler = ManageMoneyAccountHandler(repo)

    first = await handler.handle(None, _command())
    second = await handler.handle(None, _command())

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED
    assert len(repo.account_writes) == 1


@pytest.mark.asyncio
async def test_rename_resolves_target_account_id_before_persisting():
    repo = FakeAccountAdminExecutionRepository()
    handler = ManageMoneyAccountHandler(repo, resolver=FakeAccountLookupResolver())

    result = await handler.handle(
        None, _command(action="rename", name=None, target_name="Site Cash", new_name="Kochi Cash")
    )

    assert result.status == ExecutionStatus.SUCCEEDED
    assert repo.account_writes[0]["command"].target_account_id is not None


@pytest.mark.asyncio
async def test_unresolvable_rename_target_is_rejected():
    repo = FakeAccountAdminExecutionRepository()
    handler = ManageMoneyAccountHandler(
        repo, resolver=RejectingAccountLookupResolver(["no active account named 'Nonexistent'"])
    )

    result = await handler.handle(
        None, _command(action="rename", name=None, target_name="Nonexistent", new_name="X")
    )

    assert result.status == ExecutionStatus.REJECTED
    assert "no active account named 'Nonexistent'" in result.rejection_reasons
    assert repo.account_writes == []


@pytest.mark.asyncio
async def test_create_with_duplicate_name_is_rejected_by_resolver():
    repo = FakeAccountAdminExecutionRepository()
    handler = ManageMoneyAccountHandler(
        repo, resolver=RejectingAccountLookupResolver(["an account named 'Site Cash' already exists"])
    )

    result = await handler.handle(None, _command())

    assert result.status == ExecutionStatus.REJECTED
    assert repo.account_writes == []


def _confirmed(fields: dict) -> ConfirmedActionV2:
    f = {"created_by_role": "ADMIN"}
    f.update(fields)
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.MANAGE_MONEY_ACCOUNT,
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
    repo = FakeAccountAdminExecutionRepository()
    handler = ManageMoneyAccountHandler(repo, db=FakeDatabase(), resolver=FakeAccountLookupResolver())

    result = await handler.handle_confirmed(
        _confirmed({"action": "create", "name": "Site Cash", "account_type": "cash"})
    )

    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.idempotency_key == "wf_1"
    assert len(repo.account_writes) == 1


@pytest.mark.asyncio
async def test_handle_confirmed_replays_on_repeat_workflow_instance_id():
    repo = FakeAccountAdminExecutionRepository()
    handler = ManageMoneyAccountHandler(repo, db=FakeDatabase(), resolver=FakeAccountLookupResolver())
    confirmed = _confirmed({"action": "create", "name": "Site Cash"})

    first = await handler.handle_confirmed(confirmed)
    second = await handler.handle_confirmed(confirmed)

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED
    assert len(repo.account_writes) == 1
