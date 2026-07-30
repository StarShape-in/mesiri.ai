"""Unit tests for _run_member_name_gate (ENTITY_RESOLUTION_PLAN.md ADR-E1) --
resolving ADD_PROJECT_MEMBER's member_name before a draft is ever built.

Real problem this fixes: a Malayalam message named a real user who existed
under a different transliteration ("Hysam" reported, "Hisham" registered).
The name was only resolved by the backend Handler at execution time, so the
user confirmed a draft that was never capable of succeeding -- "Yes" ->
"couldn't find an active user named Hysam", with no way to retry into
success. Fakes only: no live DB.
"""

from __future__ import annotations

from typing import Any

from interactions.pending_report import PendingReportStore
from mesiri_contracts.assistant.canonical_event import CanonicalEventType, IntentCompleteness
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from runtime.inbound_journey.seeding import _run_member_name_gate
from workflows.entities import Ambiguous, Candidate, Missing, Resolved

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def namespaced(self, *parts: str) -> str:
        return ":".join(parts)

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        self._store[key] = value

    async def get_json(self, key: str) -> Any | None:
        return self._store.get(key)


def _pending_store() -> PendingReportStore:
    return PendingReportStore(_FakeRedis())


class _FakeMemberResolver:
    def __init__(self, outcome: Any, *, raises: Exception | None = None) -> None:
        self._outcome = outcome
        self._raises = raises
        self.calls: list[dict[str, Any]] = []

    async def resolve(self, *, organization_id: str, name_hint: str):
        self.calls.append({"organization_id": organization_id, "name_hint": name_hint})
        if self._raises is not None:
            raise self._raises
        return self._outcome


def _event(member_name: str = "Hysam", role: str = "project manager") -> CanonicalEventV2:
    return CanonicalEventV2(
        event_id="evt_1",
        correlation_id="cor_1",
        source_message_id="msg_1",
        event_type=CanonicalEventType.ADD_PROJECT_MEMBER_REQUESTED,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        fields={"member_name": member_name, "role": role},
    )


async def test_ignores_events_of_any_other_type():
    """This gate has one job -- everything else must pass straight through,
    untouched, without even calling the resolver."""
    from mesiri_contracts.assistant.canonical_event import CanonicalEventType as CET

    event = CanonicalEventV2(
        event_id="e",
        correlation_id="c",
        source_message_id="m",
        event_type=CET.MATERIAL_RECEIPT_REQUESTED,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        fields={"member_name": "Hysam"},
    )
    resolver = _FakeMemberResolver(Missing(name_hint="Hysam"))
    reply = await _run_member_name_gate(
        event,
        member_resolver=resolver,
        pending_report_store=_pending_store(),
        actor_user_id=USR,
        actor_role="ADMIN",
    )
    assert reply is None
    assert resolver.calls == []


async def test_resolved_falls_through_untouched():
    """An exact match: the backend's own exact-match resolver will find the
    same row again at execution (ADR-E2) -- this gate has nothing to add."""
    resolver = _FakeMemberResolver(Resolved(entity_id="u1", display_name="Hisham"))
    event = _event(member_name="Hisham")
    reply = await _run_member_name_gate(
        event,
        member_resolver=resolver,
        pending_report_store=_pending_store(),
        actor_user_id=USR,
        actor_role="ADMIN",
    )
    assert reply is None
    assert event.fields["member_name"] == "Hisham"  # unmodified


async def test_ambiguous_holds_the_report_and_offers_a_picker():
    """The live bug: "Hysam" against a real "Hisham" must become a tappable
    picker, not a dead end."""
    store = _pending_store()
    resolver = _FakeMemberResolver(
        Ambiguous(candidates=(Candidate(entity_id="u1", display_name="Hisham"),))
    )
    event = _event(member_name="Hysam")
    reply = await _run_member_name_gate(
        event,
        member_resolver=resolver,
        pending_report_store=store,
        actor_user_id=USR,
        actor_role="ADMIN",
    )
    assert reply is not None
    assert reply.list_rows is not None
    assert reply.list_rows[0].title == "Hisham"
    held = await store.pop_pending(user_id=USR)
    assert held is not None
    assert held.fields["member_name"] == "Hysam"


async def test_missing_offers_to_create_when_role_allows():
    resolver = _FakeMemberResolver(Missing(name_hint="Hysam"))
    event = _event(member_name="Hysam", role="project manager")
    reply = await _run_member_name_gate(
        event,
        member_resolver=resolver,
        pending_report_store=_pending_store(),
        actor_user_id=USR,
        actor_role="PROJECT_MANAGER",
    )
    assert reply is not None
    assert reply.buttons is not None
    assert {b.id for b in reply.buttons} == {"membernew_yes", "membernew_no"}


async def test_missing_holds_the_report_for_the_create_offer_tap():
    store = _pending_store()
    resolver = _FakeMemberResolver(Missing(name_hint="Hysam"))
    event = _event(member_name="Hysam")
    await _run_member_name_gate(
        event,
        member_resolver=resolver,
        pending_report_store=store,
        actor_user_id=USR,
        actor_role="ADMIN",
    )
    held = await store.pop_pending(user_id=USR)
    assert held is not None
    assert held.fields["member_name"] == "Hysam"


async def test_missing_refuses_the_offer_for_a_role_that_cannot_create_users():
    """A SITE_ENGINEER must never be offered CREATE_USER -- it would refuse
    them anyway (ADR-E5), and dangling an offer that always fails is worse
    than the plain not-found reply."""
    resolver = _FakeMemberResolver(Missing(name_hint="Hysam"))
    event = _event(member_name="Hysam")
    reply = await _run_member_name_gate(
        event,
        member_resolver=resolver,
        pending_report_store=_pending_store(),
        actor_user_id=USR,
        actor_role="SITE_ENGINEER",
    )
    assert reply is not None
    assert reply.buttons is None
    assert reply.list_rows is None
    assert "admin" in reply.text.lower()


async def test_missing_refuses_the_offer_for_no_role_at_all():
    resolver = _FakeMemberResolver(Missing(name_hint="Hysam"))
    event = _event(member_name="Hysam")
    reply = await _run_member_name_gate(
        event,
        member_resolver=resolver,
        pending_report_store=_pending_store(),
        actor_user_id=USR,
        actor_role=None,
    )
    assert reply is not None
    assert reply.buttons is None


async def test_a_lookup_failure_degrades_to_letting_the_event_through():
    """Never raises into the journey -- a resolver outage must not drop the
    message, same posture as every other gate in this module. The backend's
    own resolver still runs at execution and will reject honestly if the
    name really doesn't exist."""
    resolver = _FakeMemberResolver(None, raises=RuntimeError("db down"))
    event = _event(member_name="Hysam")
    reply = await _run_member_name_gate(
        event,
        member_resolver=resolver,
        pending_report_store=_pending_store(),
        actor_user_id=USR,
        actor_role="ADMIN",
    )
    assert reply is None


async def test_no_member_name_at_all_is_a_no_op():
    """canonicalization's own missing-field check already covers this case
    with CLARIFICATION_REQUIRED -- this gate has nothing to add."""
    resolver = _FakeMemberResolver(Missing(name_hint=""))
    event = _event(member_name="")
    reply = await _run_member_name_gate(
        event,
        member_resolver=resolver,
        pending_report_store=_pending_store(),
        actor_user_id=USR,
        actor_role="ADMIN",
    )
    assert reply is None
    assert resolver.calls == []
