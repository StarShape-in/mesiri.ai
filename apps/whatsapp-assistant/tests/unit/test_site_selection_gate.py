"""Unit tests for the WhatsApp site-selection gate (runtime/inbound_journey.py's
_run_site_gate and resume_pending_report_with_site).

Mirrors the project-selection gate's shape: asks "which site?" once a
project is settled but the project has more than one site. Unlike project,
site_id is never required by domain validation (domains/materials/
validation.py doesn't check it), so a hold failure fails OPEN here -- not
the project gate's fail-CLOSED, since letting an unresolved site through is
always safe. Inventory queries additionally offer "All Sites Combined"
(allow_combined=True); a material report being recorded never does.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.ports import ActorIdentity, SiteSummary
from interactions.pending_report import PendingReportStore
from mesiri_contracts.assistant.canonical_event import (
    CanonicalEventType,
    IntentCompleteness,
)
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage, SenderInfo
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from planner import Planner
from runtime.inbound_journey import _run_site_gate, resume_pending_report_with_site
from workflows import WorkflowRunResult, WorkflowRunStatus, WorkflowRuntime
from workflows.fakes import FakeWorkflowInstanceRepository, FakeWorkflowRegistry

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
OTHER_PRJ = "99999999-9999-4999-8999-999999999999"
SITE_A = "44444444-4444-4444-8444-444444444444"
SITE_B = "55555555-5555-4555-8555-555555555555"
OTHER_SITE = "66666666-6666-4666-8666-666666666666"


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def namespaced(self, *parts: str) -> str:
        return ":".join(parts)

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        self._store[key] = value

    async def get_json(self, key: str) -> Any | None:
        return self._store.get(key)


class _ExplodingRedis:
    async def namespaced(self, *parts: str) -> str:  # pragma: no cover - not exercised
        return ":".join(parts)

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        raise ConnectionError("redis unavailable")

    async def get_json(self, key: str) -> Any | None:  # pragma: no cover - not exercised
        return None


def _event(*, project_id: str | None = PRJ, site_id: str | None = None) -> CanonicalEventV2:
    return CanonicalEventV2(
        event_id="evt_1",
        correlation_id="cor_1",
        source_message_id="msg_1",
        event_type=CanonicalEventType.MATERIAL_RECEIPT_REQUESTED,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        project_id=project_id,
        site_id=site_id,
        fields={"material_name": "cement", "quantity": 50, "unit": "bags"},
    )


def _actor(*, sites: list[SiteSummary] | None = None) -> ActorIdentity:
    return ActorIdentity(
        user_id=USR,
        full_name="Engineer",
        role="SITE_ENGINEER",
        organization_id=ORG,
        org_name="Acme Construction",
        org_active=True,
        sites=sites or [],
    )


async def test_site_id_already_resolved_skips_the_gate():
    store = PendingReportStore(_FakeRedis())
    actor = _actor(sites=[SiteSummary(id=SITE_A, name="Site A", project_id=PRJ)])

    reply = await _run_site_gate(
        _event(site_id=SITE_A),
        actor=actor,
        actor_user_id=USR,
        pending_report_store=store,
        allow_combined=False,
    )

    assert reply is None
    assert await store.pop_pending(user_id=USR) is None


async def test_no_project_yet_skips_the_gate():
    """Site only makes sense once project is settled -- must not fire before
    project_id is known, even if the actor has sites."""
    store = PendingReportStore(_FakeRedis())
    actor = _actor(sites=[SiteSummary(id=SITE_A, name="Site A", project_id=PRJ)])

    reply = await _run_site_gate(
        _event(project_id=None),
        actor=actor,
        actor_user_id=USR,
        pending_report_store=store,
        allow_combined=False,
    )

    assert reply is None
    assert await store.pop_pending(user_id=USR) is None


async def test_single_site_under_project_auto_resolves():
    """Exactly one site under the resolved project -- filled in silently,
    same convenience as context/resolver.py's single-project auto-pick,
    no picker shown."""
    store = PendingReportStore(_FakeRedis())
    actor = _actor(sites=[SiteSummary(id=SITE_A, name="Site A", project_id=PRJ)])
    event = _event()

    reply = await _run_site_gate(
        event, actor=actor, actor_user_id=USR, pending_report_store=store, allow_combined=False
    )

    assert reply is None
    assert event.site_id == SITE_A
    assert await store.pop_pending(user_id=USR) is None


async def test_multiple_sites_under_project_get_picker_and_report_is_held():
    store = PendingReportStore(_FakeRedis())
    actor = _actor(
        sites=[
            SiteSummary(id=SITE_A, name="Site A", project_id=PRJ),
            SiteSummary(id=SITE_B, name="Site B", project_id=PRJ),
        ]
    )

    reply = await _run_site_gate(
        _event(), actor=actor, actor_user_id=USR, pending_report_store=store, allow_combined=False
    )

    assert reply is not None
    assert reply.list_rows is not None
    row_ids = [r.id for r in reply.list_rows]
    assert f"site_{SITE_A}" in row_ids
    assert f"site_{SITE_B}" in row_ids
    assert "site_all" not in row_ids, "recording must never offer a combined option"

    pending = await store.pop_pending(user_id=USR)
    assert pending is not None, "the event must be held pending so the tap can resume it"


async def test_inventory_query_offers_all_sites_combined():
    store = PendingReportStore(_FakeRedis())
    actor = _actor(
        sites=[
            SiteSummary(id=SITE_A, name="Site A", project_id=PRJ),
            SiteSummary(id=SITE_B, name="Site B", project_id=PRJ),
        ]
    )
    event = _event()
    event.event_type = CanonicalEventType.INVENTORY_QUERY_ASKED

    reply = await _run_site_gate(
        event, actor=actor, actor_user_id=USR, pending_report_store=store, allow_combined=True
    )

    assert reply is not None
    row_ids = [r.id for r in reply.list_rows]
    assert "site_all" in row_ids, "an inventory query must offer to combine every site"


async def test_sites_from_a_different_project_are_ignored():
    """Sites belonging to a project the report ISN'T for must not appear as
    options or count toward the single/multi-site decision."""
    store = PendingReportStore(_FakeRedis())
    actor = _actor(sites=[SiteSummary(id=OTHER_SITE, name="Other Site", project_id=OTHER_PRJ)])
    event = _event()

    reply = await _run_site_gate(
        event, actor=actor, actor_user_id=USR, pending_report_store=store, allow_combined=False
    )

    assert reply is None, "zero sites under THIS project -- report proceeds site-less"
    assert event.site_id is None


async def test_no_sites_under_project_lets_report_through_siteless():
    store = PendingReportStore(_FakeRedis())
    actor = _actor(sites=[])

    reply = await _run_site_gate(
        _event(), actor=actor, actor_user_id=USR, pending_report_store=store, allow_combined=False
    )

    assert reply is None
    assert await store.pop_pending(user_id=USR) is None


async def test_redis_failure_fails_open_unlike_the_project_gate():
    """Unlike _run_project_gate (which must fail closed since project_id is
    domain-required), site_id is never required by validation.py -- a hold
    failure here can safely let the report through site-less rather than
    blocking the user with an error."""
    store = PendingReportStore(_ExplodingRedis())
    actor = _actor(
        sites=[
            SiteSummary(id=SITE_A, name="Site A", project_id=PRJ),
            SiteSummary(id=SITE_B, name="Site B", project_id=PRJ),
        ]
    )

    reply = await _run_site_gate(
        _event(), actor=actor, actor_user_id=USR, pending_report_store=store, allow_combined=False
    )

    assert reply is None, "a hold failure must degrade gracefully, not block the report"


def _site_tap_message(row_id: str) -> NormalizedMessage:
    return NormalizedMessage(
        message_id="wamid.tap.1",
        correlation_id="cor_resume_1",
        sender=SenderInfo(wa_id="wa_engineer", profile_name="Engineer"),
        timestamp=datetime(2026, 7, 9, 10, 0, tzinfo=UTC),
        modality=InputModality.INTERACTIVE,
        metadata={"interactive_reply_id": row_id},
    )


class _RecordingWorkflowRuntime(WorkflowRuntime):
    def __init__(self) -> None:
        super().__init__(registry=FakeWorkflowRegistry(), repo=FakeWorkflowInstanceRepository())
        self.started_with_event: CanonicalEventV2 | None = None

    async def start(self, decision, event):  # type: ignore[override]
        self.started_with_event = event
        return WorkflowRunResult(
            status=WorkflowRunStatus.COMPLETED,
            workflow_key=decision.workflow_key,
            correlation_id=event.correlation_id,
            workflow_instance_id="wf_test",
            pending_prompt="done",
        )


async def test_resume_with_specific_site_tap_sets_site_id():
    store = PendingReportStore(_FakeRedis())
    await store.set_pending(user_id=USR, event=_event())
    runtime = _RecordingWorkflowRuntime()

    reply = await resume_pending_report_with_site(
        _site_tap_message(f"site_{SITE_A}"),
        USR,
        pending_report_store=store,
        planner=Planner(),
        workflow_runtime=runtime,
    )

    assert reply is not None
    assert runtime.started_with_event is not None
    assert runtime.started_with_event.site_id == SITE_A


async def test_resume_with_all_sites_combined_tap_sets_site_id_none():
    store = PendingReportStore(_FakeRedis())
    event = _event()
    event.event_type = CanonicalEventType.INVENTORY_QUERY_ASKED
    await store.set_pending(user_id=USR, event=event)
    runtime = _RecordingWorkflowRuntime()

    reply = await resume_pending_report_with_site(
        _site_tap_message("site_all"),
        USR,
        pending_report_store=store,
        planner=Planner(),
        workflow_runtime=runtime,
    )

    assert reply is not None
    assert runtime.started_with_event is not None
    assert runtime.started_with_event.site_id is None


async def test_resume_ignores_unrelated_row_ids():
    store = PendingReportStore(_FakeRedis())
    await store.set_pending(user_id=USR, event=_event())

    reply = await resume_pending_report_with_site(
        _site_tap_message("proj_p1"),
        USR,
        pending_report_store=store,
        planner=Planner(),
        workflow_runtime=_RecordingWorkflowRuntime(),
    )

    assert reply is None
    # Must not have popped the pending report for an unrelated tap.
    assert await store.pop_pending(user_id=USR) is not None
