"""Unit tests for the WhatsApp project-selection gate (runtime/inbound_journey.py's
_run_project_gate).

This is the last gate in the material/unit/project chain: it asks "which
project?" whenever a report is otherwise ACTIONABLE but has no project_id
(multi-project sender, no active/default project). domains/materials/
validation.py requires project_id -- unlike the material/unit gates, letting
an unresolved project through is never safe, so a failure here must stop the
journey with a clear reply, not silently let the report reach a confirmation
that's guaranteed to fail two steps later with "project is not resolved".
"""

from __future__ import annotations

from typing import Any

from backend.ports import ActorIdentity, ProjectSummary
from interactions.pending_report import PendingReportStore
from mesiri_contracts.assistant.canonical_event import (
    CanonicalEventType,
    IntentCompleteness,
)
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from runtime.inbound_journey import _run_project_gate

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


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
    """Simulates a Redis hiccup on the write that holds the pending report --
    the exact failure mode that used to let an unresolved report slip past
    this gate straight to confirmation."""

    async def namespaced(self, *parts: str) -> str:  # pragma: no cover - not exercised
        return ":".join(parts)

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        raise ConnectionError("redis unavailable")

    async def get_json(self, key: str) -> Any | None:  # pragma: no cover - not exercised
        return None


def _event(*, project_id: str | None = None) -> CanonicalEventV2:
    return CanonicalEventV2(
        event_id="evt_1",
        correlation_id="cor_1",
        source_message_id="msg_1",
        event_type=CanonicalEventType.MATERIAL_RECEIPT_REQUESTED,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        project_id=project_id,
        fields={"material_name": "cement", "quantity": 50, "unit": "bags"},
    )


def _actor(*, projects: list[ProjectSummary] | None = None) -> ActorIdentity:
    return ActorIdentity(
        user_id=USR,
        full_name="Engineer",
        role="SITE_ENGINEER",
        organization_id=ORG,
        org_name="Acme Construction",
        org_active=True,
        projects=projects or [],
    )


async def test_project_id_already_resolved_skips_the_gate():
    """A report that already carries a project_id must not be held or asked
    about -- the gate is a no-op in this case."""
    project_id = "33333333-3333-4333-8333-333333333333"
    store = PendingReportStore(_FakeRedis())
    actor = _actor(projects=[ProjectSummary(id=project_id, name="Site A")])

    reply = await _run_project_gate(
        _event(project_id=project_id), actor=actor, actor_user_id=USR, pending_report_store=store
    )

    assert reply is None
    assert await store.pop_pending(user_id=USR) is None


async def test_multi_project_actor_gets_picker_and_report_is_held():
    """The normal path: no project_id, actor has more than one project ->
    a picker is returned and the report is held so the tap can resume it."""
    store = PendingReportStore(_FakeRedis())
    actor = _actor(
        projects=[
            ProjectSummary(id="p1", name="Site A"),
            ProjectSummary(id="p2", name="Site B"),
        ]
    )

    reply = await _run_project_gate(
        _event(), actor=actor, actor_user_id=USR, pending_report_store=store
    )

    assert reply is not None
    assert reply.list_rows is not None
    row_ids = [r.id for r in reply.list_rows]
    assert "proj_p1" in row_ids
    assert "proj_p2" in row_ids

    pending = await store.pop_pending(user_id=USR)
    assert pending is not None, "the event must be held pending so the tap can resume it"


async def test_actor_with_no_projects_gets_no_projects_reply_without_holding():
    """No projects at all -- tapping wouldn't help, so this is a plain
    message, not a picker, and nothing is held pending."""
    store = PendingReportStore(_FakeRedis())
    actor = _actor(projects=[])

    reply = await _run_project_gate(
        _event(), actor=actor, actor_user_id=USR, pending_report_store=store
    )

    assert reply is not None
    assert reply.list_rows is None
    assert await store.pop_pending(user_id=USR) is None


async def test_redis_failure_while_holding_fails_closed_not_open():
    """Regression test: if pending_report_store.set_pending() raises (e.g. a
    Redis hiccup) while trying to hold the report for the project picker, the
    gate must NOT silently let the ACTIONABLE-but-project-less event fall
    through to the planner/confirmation -- project_id is required by
    domains/materials/validation.py, so that would only defer a guaranteed
    failure to right after the user taps Yes ("project is not resolved").
    The gate must instead return a reply that stops the journey here."""
    store = PendingReportStore(_ExplodingRedis())
    actor = _actor(
        projects=[
            ProjectSummary(id="p1", name="Site A"),
            ProjectSummary(id="p2", name="Site B"),
        ]
    )

    reply = await _run_project_gate(
        _event(), actor=actor, actor_user_id=USR, pending_report_store=store
    )

    assert reply is not None, (
        "a hold failure must stop the journey with a reply, not silently return None "
        "and let an unresolved report reach confirmation"
    )
    assert reply.list_rows is None, "no picker was actually held, so this must not claim to be one"
    assert "project" in reply.text.lower()
