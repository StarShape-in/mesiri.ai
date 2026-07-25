"""ReverseTransactionHandler — unit tests (fakes only, no DB)."""

from __future__ import annotations

import pytest

from mesiri.application.finance.reverse_commands import ReverseTransactionCommand
from mesiri.application.finance.reverse_fakes import (
    FakeDatabase,
    FakeReverseExecutionRepository,
    FakeReverseTargetResolver,
    RejectingReverseTargetResolver,
)
from mesiri.application.finance.reverse_handler import ReverseTransactionHandler
from mesiri_contracts.application.results.execution_result import ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
EXPENSE_ID = "55555555-5555-4555-8555-555555555555"


def _command(**overrides) -> ReverseTransactionCommand:
    base = dict(
        idempotency_key="idem_1",
        organization_id=ORG,
        created_by=USR,
        created_by_role="ADMIN",
        target_kind="expense",
        expense_id=EXPENSE_ID,
    )
    base.update(overrides)
    return ReverseTransactionCommand(**base)


@pytest.mark.asyncio
async def test_valid_command_succeeds_and_persists_one_row():
    repo = FakeReverseExecutionRepository()
    handler = ReverseTransactionHandler(repo, resolver=FakeReverseTargetResolver())

    result = await handler.handle(None, _command())

    assert result.status == ExecutionStatus.SUCCEEDED
    assert len(repo.reversal_writes) == 1


@pytest.mark.asyncio
async def test_disallowed_role_is_rejected_without_persisting():
    repo = FakeReverseExecutionRepository()
    handler = ReverseTransactionHandler(repo, resolver=FakeReverseTargetResolver())

    result = await handler.handle(None, _command(created_by_role="SITE_ENGINEER"))

    assert result.status == ExecutionStatus.REJECTED
    assert "only an admin or finance user can reverse a transaction" in result.rejection_reasons
    assert repo.reversal_writes == []


@pytest.mark.asyncio
async def test_repeated_idempotency_key_replays_without_second_write():
    repo = FakeReverseExecutionRepository()
    handler = ReverseTransactionHandler(repo, resolver=FakeReverseTargetResolver())

    first = await handler.handle(None, _command())
    second = await handler.handle(None, _command())

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED
    assert len(repo.reversal_writes) == 1


@pytest.mark.asyncio
async def test_resolver_rejection_stops_persistence():
    """The already-reversed/already-voided defense-in-depth check runs even
    when the command structurally validates fine."""
    repo = FakeReverseExecutionRepository()
    handler = ReverseTransactionHandler(
        repo, resolver=RejectingReverseTargetResolver(["that expense is already voided"])
    )

    result = await handler.handle(None, _command())

    assert result.status == ExecutionStatus.REJECTED
    assert "that expense is already voided" in result.rejection_reasons
    assert repo.reversal_writes == []


@pytest.mark.asyncio
async def test_resolver_is_not_consulted_for_a_structurally_invalid_command():
    repo = FakeReverseExecutionRepository()
    handler = ReverseTransactionHandler(
        repo, resolver=RejectingReverseTargetResolver(["should never be seen"])
    )

    result = await handler.handle(None, _command(created_by_role="SITE_ENGINEER"))

    assert result.status == ExecutionStatus.REJECTED
    assert result.rejection_reasons == ["only an admin or finance user can reverse a transaction"]


def _confirmed(fields: dict) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.REVERSE_TRANSACTION,
        organization_id=ORG,
        user_id=USR,
        fields=fields,
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )


@pytest.mark.asyncio
async def test_handle_confirmed_maps_and_persists():
    repo = FakeReverseExecutionRepository()
    handler = ReverseTransactionHandler(
        repo, db=FakeDatabase(), resolver=FakeReverseTargetResolver()
    )

    result = await handler.handle_confirmed(
        _confirmed({"target_kind": "expense", "expense_id": EXPENSE_ID, "created_by_role": "ADMIN"})
    )

    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.idempotency_key == "wf_1"
    assert len(repo.reversal_writes) == 1


@pytest.mark.asyncio
async def test_handle_confirmed_replays_on_repeat_workflow_instance_id():
    repo = FakeReverseExecutionRepository()
    handler = ReverseTransactionHandler(
        repo, db=FakeDatabase(), resolver=FakeReverseTargetResolver()
    )
    confirmed = _confirmed(
        {"target_kind": "expense", "expense_id": EXPENSE_ID, "created_by_role": "ADMIN"}
    )

    first = await handler.handle_confirmed(confirmed)
    second = await handler.handle_confirmed(confirmed)

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED
    assert len(repo.reversal_writes) == 1
