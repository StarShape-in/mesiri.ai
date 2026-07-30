"""_run_petty_cash_recipient_gate -- Phase 4 of ENTITY_RESOLUTION_PLAN.md §5.

The defect this closes is ADR-E1's, in the workflow where it costs the most:
until now the only lookup for a petty-cash recipient was
`find_by_full_name_active` (exact, case-insensitive) inside
_seed_petty_cash_recipient. A near-miss -- §1's ഹൈസം/"Hysam" against a real
"Hisham" -- resolved to nothing, so `recipient_account_id` stayed unset,
build_draft produced a draft missing that leg of the transfer, and
transfer_validation.py rejected it *after* the user had already tapped Yes.
A doomed confirmation, for the one workflow whose confirmation moves money.

Fakes only: no live DB.
"""

from __future__ import annotations

from typing import Any

from mesiri_contracts.assistant.canonical_event import (
    CanonicalEventType,
    IntentCompleteness,
)
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from runtime.entity_resolution.name_matching import NamedCandidate, resolve_name_hint
from runtime.inbound_journey import _run_petty_cash_recipient_gate

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


def _pending_store():
    from interactions.pending_report import PendingReportStore

    return PendingReportStore(_FakeRedis())


class _FakeResolver:
    """Runs the real scorer over a canned roster, so these cover the actual
    matching rule rather than a hand-stubbed outcome."""

    def __init__(self, *names: str, raises: bool = False) -> None:
        self._candidates = [
            NamedCandidate(entity_id=f"u_{i}", display_name=n) for i, n in enumerate(names)
        ]
        self._raises = raises

    async def resolve(self, *, organization_id: str, name_hint: str):
        if self._raises:
            raise RuntimeError("db down")
        return resolve_name_hint(name_hint, self._candidates)


def _event(
    recipient: str | None = "Hysam",
    event_type: CanonicalEventType = CanonicalEventType.PETTY_CASH_ISSUE_REQUESTED,
) -> CanonicalEventV2:
    fields: dict[str, Any] = {"amount": 5000}
    if recipient is not None:
        fields["recipient_name"] = recipient
    return CanonicalEventV2(
        event_id="evt_1",
        correlation_id="cor_1",
        source_message_id="msg_1",
        event_type=event_type,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        fields=fields,
    )


async def test_an_exact_recipient_passes_through_with_the_stored_spelling():
    event = _event(recipient="hisham")
    reply = await _run_petty_cash_recipient_gate(
        event,
        member_resolver=_FakeResolver("Hisham"),
        pending_report_store=_pending_store(),
        actor_user_id=USR,
    )

    assert reply is None, "an exact match must not interrupt the issuance"
    # Rewritten so _seed_petty_cash_recipient's own exact lookup finds the
    # same row rather than missing on case/spacing.
    assert event.fields["recipient_name"] == "Hisham"


async def test_a_near_miss_asks_who_the_cash_is_for_instead_of_failing_late():
    """The live bug: this used to sail through to a confirmation that could
    only ever be rejected."""
    event = _event(recipient="Hysam")
    store = _pending_store()
    reply = await _run_petty_cash_recipient_gate(
        event,
        member_resolver=_FakeResolver("Hisham"),
        pending_report_store=store,
        actor_user_id=USR,
    )

    assert reply is not None
    assert reply.list_rows is not None
    assert [r.id for r in reply.list_rows] == ["pcr_u_0", "pcr_none"]
    assert "Hysam" in reply.text
    # Never silently adopted -- the user picks.
    assert event.fields["recipient_name"] == "Hysam"
    assert await store.pop_pending(user_id=USR) is not None, "the request must be held for the tap"


async def test_the_picker_always_offers_a_way_out():
    """Phase 3's lesson (§5.1): an Ambiguous that cannot be declined is a
    trap. Doubly so here -- the wrong tap credits the wrong person's account."""
    reply = await _run_petty_cash_recipient_gate(
        _event(recipient="Hysam"),
        member_resolver=_FakeResolver("Hisham"),
        pending_report_store=_pending_store(),
        actor_user_id=USR,
    )

    assert reply.list_rows[-1].id == "pcr_none"
    assert reply.list_rows[-1].title == "None of these"


async def test_an_unknown_recipient_stops_here_rather_than_building_a_doomed_draft():
    event = _event(recipient="Nobody At All")
    reply = await _run_petty_cash_recipient_gate(
        event,
        member_resolver=_FakeResolver("Hisham"),
        pending_report_store=_pending_store(),
        actor_user_id=USR,
    )

    assert reply is not None
    assert reply.list_rows is None
    assert "couldn't find" in reply.text.lower()
    # Deliberately NOT a create offer, unlike the member gate's Missing case:
    # issuing cash is a poor moment to also be creating the payee.
    assert reply.buttons is None


async def test_a_return_leg_is_gated_too():
    """A return debits the same advance account, so it needs the recipient
    resolved for the same reason an issue does."""
    event = _event(
        recipient="hisham", event_type=CanonicalEventType.PETTY_CASH_RETURN_REQUESTED
    )
    reply = await _run_petty_cash_recipient_gate(
        event,
        member_resolver=_FakeResolver("Hisham"),
        pending_report_store=_pending_store(),
        actor_user_id=USR,
    )

    assert reply is None
    assert event.fields["recipient_name"] == "Hisham"


async def test_an_unrelated_event_is_left_alone():
    event = _event(event_type=CanonicalEventType.EXPENSE_REQUESTED)
    reply = await _run_petty_cash_recipient_gate(
        event,
        member_resolver=_FakeResolver("Hisham"),
        pending_report_store=_pending_store(),
        actor_user_id=USR,
    )
    assert reply is None


async def test_no_recipient_named_is_left_alone():
    reply = await _run_petty_cash_recipient_gate(
        _event(recipient=None),
        member_resolver=_FakeResolver("Hisham"),
        pending_report_store=_pending_store(),
        actor_user_id=USR,
    )
    assert reply is None


async def test_a_lookup_failure_never_loses_the_request():
    """Fail-soft, same posture as every other gate -- the pre-existing
    validation still rejects honestly downstream."""
    event = _event(recipient="Hysam")
    reply = await _run_petty_cash_recipient_gate(
        event,
        member_resolver=_FakeResolver("Hisham", raises=True),
        pending_report_store=_pending_store(),
        actor_user_id=USR,
    )

    assert reply is None
    assert event.fields["recipient_name"] == "Hysam"
