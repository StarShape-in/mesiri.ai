"""ActionTypeRoutingDispatcher — unit tests (fakes only, no DB)."""

from __future__ import annotations

import pytest

from interactions.execution_router import ActionTypeRoutingDispatcher
from mesiri_contracts.application.results.execution_result import ExecutionResult, ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _confirmed(action_type: DraftActionType) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id="wf_1",
        action_type=action_type,
        organization_id=ORG,
        user_id=USR,
        fields={},
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=USR,
    )


class _StubDispatcher:
    def __init__(self, result: ExecutionResult) -> None:
        self._result = result
        self.calls = 0

    async def dispatch(self, confirmed: ConfirmedActionV2) -> ExecutionResult:
        self.calls += 1
        return self._result


@pytest.mark.asyncio
async def test_routes_to_the_dispatcher_registered_for_action_type():
    expense_result = ExecutionResult(
        status=ExecutionStatus.SUCCEEDED, idempotency_key="wf_1", material_row_id="row_1"
    )
    material_dispatcher = _StubDispatcher(
        ExecutionResult(status=ExecutionStatus.SUCCEEDED, idempotency_key="wf_1", material_row_id="row_2")
    )
    expense_dispatcher = _StubDispatcher(expense_result)
    router = ActionTypeRoutingDispatcher(
        {
            DraftActionType.RECORD_MATERIAL_RECEIPT: material_dispatcher,
            DraftActionType.RECORD_EXPENSE: expense_dispatcher,
        }
    )

    result = await router.dispatch(_confirmed(DraftActionType.RECORD_EXPENSE))

    assert result is expense_result
    assert expense_dispatcher.calls == 1
    assert material_dispatcher.calls == 0


@pytest.mark.asyncio
async def test_unregistered_action_type_reports_failed_without_raising():
    router = ActionTypeRoutingDispatcher({})

    result = await router.dispatch(_confirmed(DraftActionType.RECORD_EXPENSE))

    assert result.status == ExecutionStatus.FAILED
    assert result.idempotency_key == "wf_1"
