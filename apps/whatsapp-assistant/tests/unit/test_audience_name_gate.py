"""_run_audience_name_gate -- Phase 4 of ENTITY_RESOLUTION_PLAN.md §5.

"remind Ilan and Hysam every Monday to send site photos" used to travel all
the way to application/automations/handlers.py, which resolved the names via
find_by_full_name_active (exact) at persist time and rejected the whole
command listing any it missed. So the user saw a confirmation, tapped Yes,
and only then got "couldn't find: Hysam" -- another doomed confirmation, and
§1's transliteration bug again.

Resolved names are asked about one at a time so the request survives an
unknown name instead of needing the whole sentence retyped.

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
from runtime.inbound_journey import _run_audience_name_gate

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
    audience_names: list[str] | None = None,
    event_type: CanonicalEventType = CanonicalEventType.AUTOMATION_SETUP_REQUESTED,
) -> CanonicalEventV2:
    fields: dict[str, Any] = {"audience": "USERS"}
    if audience_names is not None:
        fields["audience_names"] = audience_names
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


async def _run(event, resolver, store=None):
    return await _run_audience_name_gate(
        event,
        member_resolver=resolver,
        pending_report_store=store or _pending_store(),
        actor_user_id=USR,
    )


async def test_all_names_exact_passes_through_with_stored_spellings():
    event = _event(["ilan  usman", "hisham"])
    reply = await _run(event, _FakeResolver("Ilan Usman", "Hisham"))

    assert reply is None
    # Rewritten so the Handler's own exact lookup finds the same rows.
    assert event.fields["audience_names"] == ["Ilan Usman", "Hisham"]


async def test_a_near_miss_asks_about_that_one_name_only():
    """"remind Ilan and Hysam" -- Ilan is settled, so the question is only
    about Hysam."""
    event = _event(["Ilan", "Hysam"])
    store = _pending_store()
    reply = await _run(event, _FakeResolver("Ilan", "Hisham"), store)

    assert reply is not None
    assert "Hysam" in reply.text
    assert "Ilan" not in reply.text, "a name already settled must not be re-asked"
    assert [r.id for r in reply.list_rows] == ["aud_u_1", "aud_none"]
    assert await store.pop_pending(user_id=USR) is not None


async def test_the_already_resolved_names_are_kept_while_asking():
    """Answering must not re-ask about names already agreed on, so the
    resolved spellings are persisted onto the held event."""
    event = _event(["ilan usman", "Hysam"])
    await _run(event, _FakeResolver("Ilan Usman", "Hisham"))

    assert event.fields["audience_names"][0] == "Ilan Usman"
    assert event.fields["audience_names"][1] == "Hysam"
    assert event.fields["_audience_pending_name"] == "Hysam"


async def test_the_picker_always_offers_a_way_out():
    reply = await _run(_event(["Hysam"]), _FakeResolver("Hisham"))
    assert reply.list_rows[-1].id == "aud_none"
    assert reply.list_rows[-1].title == "None of these"


async def test_a_completely_unknown_name_stops_rather_than_reminding_everyone_else():
    """Creating the automation without them would fail silently -- nobody
    finds out until the reminder they needed never arrived."""
    event = _event(["Ilan", "Nobody At All"])
    reply = await _run(event, _FakeResolver("Ilan", "Hisham"))

    assert reply is not None
    assert reply.list_rows is None
    assert "couldn't find" in reply.text.lower()
    assert "Nobody At All" in reply.text
    # No stale marker left behind on a stopped request.
    assert "_audience_pending_name" not in event.fields


async def test_the_pending_marker_never_survives_a_clean_pass():
    """It is plumbing -- it must not reach CreateAutomationCommand."""
    event = _event(["ilan usman"])
    event.fields["_audience_pending_name"] = "stale"
    reply = await _run(event, _FakeResolver("Ilan Usman"))

    assert reply is None
    assert "_audience_pending_name" not in event.fields


async def test_a_self_digest_with_no_named_audience_is_left_alone():
    reply = await _run(_event(None), _FakeResolver("Ilan"))
    assert reply is None


async def test_an_empty_audience_list_is_left_alone():
    reply = await _run(_event([]), _FakeResolver("Ilan"))
    assert reply is None


async def test_an_unrelated_event_is_left_alone():
    event = _event(["Hysam"], event_type=CanonicalEventType.EXPENSE_REQUESTED)
    reply = await _run(event, _FakeResolver("Hisham"))
    assert reply is None


async def test_a_lookup_failure_never_loses_the_automation():
    event = _event(["Hysam"])
    reply = await _run(event, _FakeResolver("Hisham", raises=True))

    assert reply is None
    assert event.fields["audience_names"] == ["Hysam"]


async def test_a_bare_first_name_is_offered_rather_than_declared_missing():
    """The gap this surfaced: "remind Ilan" against a roster holding "Ilan
    Usman" scored 0.571 -- under the 0.6 ask threshold -- and came back
    "I couldn't find Ilan" about someone plainly in the org. Whether it
    worked depended on how long the surname was, which is not a rule anyone
    could have predicted."""
    event = _event(["Ilan"])
    reply = await _run(event, _FakeResolver("Ilan Usman"))

    assert reply is not None
    assert [r.id for r in reply.list_rows] == ["aud_u_0", "aud_none"]
    assert "Ilan Usman" in reply.list_rows[0].title
