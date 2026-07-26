"""The temporary Labour persistence stub — unit tests.

Small on purpose. This module is scaffolding scheduled for deletion in Phase
5, so these tests pin only the two things that would actually hurt if they
broke: confirming an attendance must not error (that would hide the
conversation we are trying to validate), and it must be loudly identifiable
as not-a-real-record.
"""

from __future__ import annotations

import logging

from mesiri_contracts.application.results.execution_result import ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from runtime.labour_execution_stub import StubLabourExecutionDispatcher

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
WORKER = "55555555-5555-4555-8555-555555555555"


def _confirmed(fields: dict) -> ConfirmedActionV2:
    return ConfirmedActionV2(
        confirmed_action_id="confirmed_1",
        workflow_instance_id="wf_1",
        correlation_id="cor_1",
        confirmed_by_user_id=USR,
        draft_action=DraftActionV2(
            draft_id="draft_1",
            correlation_id="cor_1",
            workflow_instance_id="wf_1",
            action_type=DraftActionType.RECORD_LABOUR_ATTENDANCE,
            organization_id=ORG,
            user_id=USR,
            project_id=PRJ,
            fields=fields,
        ),
    )


async def test_confirming_an_attendance_succeeds_rather_than_erroring():
    """Without this, ActionTypeRoutingDispatcher returns FAILED and the user
    sees an error at the exact moment we are trying to observe."""
    result = await StubLabourExecutionDispatcher().dispatch(
        _confirmed({"lines": [{"worker_name": None, "trade": "helper", "headcount": 12}]})
    )
    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.idempotency_key == "wf_1"


async def test_the_row_id_is_visibly_not_a_real_record():
    result = await StubLabourExecutionDispatcher().dispatch(_confirmed({"lines": []}))
    assert result.material_row_id.startswith("stub-")


async def test_it_warns_loudly_with_a_readable_summary(caplog):
    """The gap must be observable in the control panel, not silent."""
    with caplog.at_level(logging.WARNING):
        await StubLabourExecutionDispatcher().dispatch(
            _confirmed(
                {
                    "lines": [
                        {"worker_name": "Ravi", "trade": "mason", "headcount": 1, "worker_id": WORKER},
                        {"worker_name": "Arun", "trade": "painter", "headcount": 1},
                        {"worker_name": None, "trade": "helper", "headcount": 12},
                    ]
                }
            )
        )
    record = caplog.text
    assert "NOT PERSISTED" in record
    assert "14 workers" in record
    assert "Ravi(mason,matched)" in record
    assert "Arun(painter,temporary)" in record
    assert "12xhelper" in record


async def test_an_empty_attendance_does_not_crash_the_summary():
    result = await StubLabourExecutionDispatcher().dispatch(_confirmed({}))
    assert result.status is ExecutionStatus.SUCCEEDED
