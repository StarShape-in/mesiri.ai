"""TransferMoneyHandler — unit tests (fakes only, no DB)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from mesiri.application.finance.transfer_commands import TransferMoneyCommand
from mesiri.application.finance.transfer_fakes import (
    FakeDatabase,
    FakeTransferAccountResolver,
    FakeTransferExecutionRepository,
    RejectingTransferAccountResolver,
)
from mesiri.application.finance.transfer_handler import TransferMoneyHandler
from mesiri_contracts.application.results.execution_result import ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
ACC_A = "55555555-5555-4555-8555-555555555555"
ACC_B = "66666666-6666-4666-8666-666666666666"


def _command(**overrides) -> TransferMoneyCommand:
    base = dict(
        idempotency_key="idem_1",
        organization_id=ORG,
        created_by=USR,
        created_by_role="ADMIN",
        from_account_id=ACC_A,
        to_account_id=ACC_B,
        amount=Decimal("500.00"),
        occurred_date=date.today(),
    )
    base.update(overrides)
    return TransferMoneyCommand(**base)


@pytest.mark.asyncio
async def test_valid_transfer_succeeds_and_persists_one_row():
    repo = FakeTransferExecutionRepository()
    handler = TransferMoneyHandler(repo, resolver=FakeTransferAccountResolver())

    result = await handler.handle(None, _command())

    assert result.status == ExecutionStatus.SUCCEEDED
    assert len(repo.ledger_writes) == 1


@pytest.mark.asyncio
async def test_structurally_invalid_command_is_rejected_without_resolver_call():
    repo = FakeTransferExecutionRepository()
    handler = TransferMoneyHandler(
        repo, resolver=RejectingTransferAccountResolver(["should never be seen"])
    )

    result = await handler.handle(None, _command(amount=Decimal("0")))

    assert result.status == ExecutionStatus.REJECTED
    assert "amount must be greater than zero" in result.rejection_reasons
    assert repo.ledger_writes == []


@pytest.mark.asyncio
async def test_inactive_account_is_rejected_by_resolver():
    repo = FakeTransferExecutionRepository()
    handler = TransferMoneyHandler(
        repo, resolver=RejectingTransferAccountResolver(["the source account is not active"])
    )

    result = await handler.handle(None, _command())

    assert result.status == ExecutionStatus.REJECTED
    assert "the source account is not active" in result.rejection_reasons
    assert repo.ledger_writes == []


@pytest.mark.asyncio
async def test_repeated_idempotency_key_replays_without_second_write():
    repo = FakeTransferExecutionRepository()
    handler = TransferMoneyHandler(repo, resolver=FakeTransferAccountResolver())

    first = await handler.handle(None, _command())
    second = await handler.handle(None, _command())

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED
    assert len(repo.ledger_writes) == 1


def _confirmed(fields: dict) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=DraftActionType.TRANSFER_MONEY,
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
async def test_handle_confirmed_maps_and_persists_end_to_end():
    repo = FakeTransferExecutionRepository()
    handler = TransferMoneyHandler(repo, db=FakeDatabase(), resolver=FakeTransferAccountResolver())

    result = await handler.handle_confirmed(
        _confirmed(
            {
                "amount": 500,
                "from_account_id": ACC_A,
                "to_account_id": ACC_B,
                "created_by_role": "ADMIN",
            }
        )
    )

    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.idempotency_key == "wf_1"
    assert len(repo.ledger_writes) == 1


@pytest.mark.asyncio
async def test_handle_confirmed_replays_on_repeat_workflow_instance_id():
    repo = FakeTransferExecutionRepository()
    handler = TransferMoneyHandler(repo, db=FakeDatabase(), resolver=FakeTransferAccountResolver())
    confirmed = _confirmed(
        {"amount": 500, "from_account_id": ACC_A, "to_account_id": ACC_B, "created_by_role": "ADMIN"}
    )

    first = await handler.handle_confirmed(confirmed)
    second = await handler.handle_confirmed(confirmed)

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED
    assert len(repo.ledger_writes) == 1
