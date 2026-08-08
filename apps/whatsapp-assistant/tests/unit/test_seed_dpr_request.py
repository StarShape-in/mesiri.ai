"""_seed_dpr_request -- #16 Daily Report Generation's chat-trigger seeding.

Mirrors test_seed_activity_search.py's shape: a fake DprRequestQueryService
stands in for the real Postgres-backed one. What's protected here is pure
wiring: DPR_REQUEST resolves "today" for the sender's timezone and writes
the three fields (dpr_status/dpr_object_key/dpr_code) the node and the
post-reply document-delivery step both read.
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
from runtime.inbound_journey import _seed_dpr_request

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"


class _Actor:
    organization_id = ORG
    user_id = USR
    role = "site_engineer"


class _FakeDprRequestQueryService:
    def __init__(self, result: dict):
        self._result = result
        self.calls: list[dict] = []

    async def find_report(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self._result)


def _decision(workflow_key: WorkflowKey, reason: CanonicalEventType) -> PlannerDecisionV2:
    return PlannerDecisionV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        decision_type=PlannerDecisionType.START_WORKFLOW,
        workflow_key=workflow_key,
        reason=reason,
        priority=PlannerPriority.NORMAL,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=SITE,
    )


def _event(event_type: CanonicalEventType, fields: dict) -> CanonicalEventV2:
    return CanonicalEventV2(
        event_id="evt_1",
        correlation_id="cor_1",
        source_message_id="msg_1",
        event_type=event_type,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=SITE,
        fields=fields,
    )


async def test_ready_report_seeds_status_object_key_and_code():
    service = _FakeDprRequestQueryService(
        {"status": "ready", "object_key": "dpr/report-1/version-1.pdf", "code": "DPR-20260727-AB12"}
    )
    event = _event(CanonicalEventType.DPR_REQUESTED, {})
    decision = _decision(WorkflowKey.DPR_REQUEST, CanonicalEventType.DPR_REQUESTED)

    await _seed_dpr_request(event, decision, service, _Actor(), "Asia/Kolkata")

    assert len(service.calls) == 1
    call = service.calls[0]
    assert call["organization_id"] == ORG
    assert call["project_id"] == PRJ
    assert call["site_id"] == SITE
    assert event.fields["dpr_status"] == "ready"
    assert event.fields["dpr_object_key"] == "dpr/report-1/version-1.pdf"
    assert event.fields["dpr_code"] == "DPR-20260727-AB12"


async def test_not_generated_report_seeds_none_object_key():
    service = _FakeDprRequestQueryService({"status": "not_generated", "object_key": None, "code": None})
    event = _event(CanonicalEventType.DPR_REQUESTED, {})
    decision = _decision(WorkflowKey.DPR_REQUEST, CanonicalEventType.DPR_REQUESTED)

    await _seed_dpr_request(event, decision, service, _Actor(), "Asia/Kolkata")

    assert event.fields["dpr_status"] == "not_generated"
    assert event.fields["dpr_object_key"] is None


async def test_is_a_no_op_for_a_different_workflow():
    service = _FakeDprRequestQueryService({"status": "ready", "object_key": "x", "code": "y"})
    event = _event(CanonicalEventType.ACTIVITY_QUERY_ASKED, {})
    decision = _decision(WorkflowKey.ACTIVITY_QUERY, CanonicalEventType.ACTIVITY_QUERY_ASKED)

    await _seed_dpr_request(event, decision, service, _Actor(), "Asia/Kolkata")

    assert service.calls == []
    assert "dpr_status" not in event.fields


async def test_is_a_safe_no_op_with_no_service_wired():
    event = _event(CanonicalEventType.DPR_REQUESTED, {})
    decision = _decision(WorkflowKey.DPR_REQUEST, CanonicalEventType.DPR_REQUESTED)

    await _seed_dpr_request(event, decision, None, _Actor(), "Asia/Kolkata")

    assert "dpr_status" not in event.fields
