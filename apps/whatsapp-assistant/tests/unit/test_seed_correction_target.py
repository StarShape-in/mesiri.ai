"""_seed_correction_target -- unit tests.

Mirrors test_seed_open_activity.py's shape: a fake ActivityQueryService
stands in for the Postgres-backed one. ADR-D14: "make that 180" is scoped
to the Activity THIS conversation just touched only (same reasoning as
undo/ADR-D15 and continuation's _seed_open_activity), never a broader
"most recent in the org" search.
"""

from __future__ import annotations

from mesiri_contracts.assistant.canonical_event import CanonicalEventType, IntentCompleteness
from mesiri_contracts.assistant.planner_decision import (
    PlannerDecisionType,
    PlannerPriority,
    WorkflowKey,
)
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from runtime.inbound_journey import _seed_correction_target

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"
ACTIVITY_ID = "55555555-5555-4555-8555-555555555555"
PROGRESS_UPDATE_ID = "66666666-6666-4666-8666-666666666666"


class _Actor:
    organization_id = ORG
    user_id = USR
    role = "site_engineer"


class _FakeActivityQueryService:
    def __init__(self, *, target: dict | None = None):
        self._target = target
        self.calls: list[dict] = []

    async def get_latest_quantity_update(self, **kwargs):
        self.calls.append(kwargs)
        return self._target


def _decision(workflow_key: WorkflowKey = WorkflowKey.ACTIVITY_CORRECTION) -> PlannerDecisionV2:
    return PlannerDecisionV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        decision_type=PlannerDecisionType.START_WORKFLOW,
        workflow_key=workflow_key,
        reason=CanonicalEventType.ACTIVITY_CORRECTION_REQUESTED,
        priority=PlannerPriority.NORMAL,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=SITE,
    )


def _event(fields: dict) -> CanonicalEventV2:
    return CanonicalEventV2(
        event_id="evt_1",
        correlation_id="cor_1",
        source_message_id="msg_1",
        event_type=CanonicalEventType.ACTIVITY_CORRECTION_REQUESTED,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=SITE,
        fields=fields,
    )


async def test_seeds_target_from_the_remembered_activity():
    service = _FakeActivityQueryService(
        target={
            "progress_update_id": PROGRESS_UPDATE_ID,
            "quantity": "80",
            "unit_id": "unit-1",
            "unit": "sqm",
            "work_type": "plastering",
            "narrative": "2nd floor",
        }
    )
    event = _event({"new_quantity": 180, "unit": "sqm"})
    decision = _decision()

    await _seed_correction_target(event, decision, service, _Actor(), remembered_activity_id=ACTIVITY_ID)

    assert event.fields["progress_update_id"] == PROGRESS_UPDATE_ID
    assert event.fields["old_quantity"] == "80"
    assert event.fields["old_unit"] == "sqm"
    assert event.fields["correction_activity_summary"] == "plastering — 2nd floor"
    assert service.calls == [{"organization_id": ORG, "activity_id": ACTIVITY_ID}]


async def test_no_remembered_activity_seeds_nothing():
    """ADR-D14: correction is scoped to the Activity THIS conversation just
    touched only -- a first message of the day (nothing remembered yet)
    must not fall back to a broader search."""
    service = _FakeActivityQueryService(target={"progress_update_id": PROGRESS_UPDATE_ID})
    event = _event({"new_quantity": 180, "unit": "sqm"})
    decision = _decision()

    await _seed_correction_target(event, decision, service, _Actor())

    assert "progress_update_id" not in event.fields
    assert service.calls == []


async def test_no_quantity_bearing_update_seeds_nothing():
    service = _FakeActivityQueryService(target=None)
    event = _event({"new_quantity": 180, "unit": "sqm"})
    decision = _decision()

    await _seed_correction_target(event, decision, service, _Actor(), remembered_activity_id=ACTIVITY_ID)

    assert "progress_update_id" not in event.fields


async def test_is_a_no_op_for_a_different_workflow():
    service = _FakeActivityQueryService(target={"progress_update_id": PROGRESS_UPDATE_ID})
    event = _event({"new_quantity": 180, "unit": "sqm"})
    decision = _decision(WorkflowKey.SITE_UPDATE)

    await _seed_correction_target(event, decision, service, _Actor(), remembered_activity_id=ACTIVITY_ID)

    assert service.calls == []
    assert "progress_update_id" not in event.fields


async def test_is_a_safe_no_op_with_no_service_wired():
    event = _event({"new_quantity": 180, "unit": "sqm"})
    decision = _decision()

    await _seed_correction_target(event, decision, None, _Actor(), remembered_activity_id=ACTIVITY_ID)

    assert "progress_update_id" not in event.fields
