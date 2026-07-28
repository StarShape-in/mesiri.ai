"""Worker promotion workflow node — unit tests (pure function, no LangGraph needed).

Mirrors tests/unit/test_labour_update_nodes.py's style: the node is re-entrant
and has no memory between passes, so tests spanning two messages thread
`collected_fields` and `awaiting_slot` through by hand, exactly as
WorkflowRuntime.provide_input does.
"""

from __future__ import annotations

from workflows.worker_promotion.nodes import (
    DUPLICATE_SLOT,
    PROMOTION_SLOT,
    offer_and_promote,
)

AJITH = {"name": "Ajith", "trade": "mason", "daily_wage": "800"}
NIYAS = {"name": "Niyas", "trade": "helper", "daily_wage": "600"}
RAHUL = {"name": "Rahul", "trade": "painter", "daily_wage": "700"}


def _base_state(fields: dict, **extra) -> dict:
    state = {
        "workflow_instance_id": "wf_promo_1",
        "workflow_key": "labour.worker_promotion",
        "correlation_id": "cor_1",
        "organization_id": "org1",
        "user_id": "usr1",
        "project_id": "prj1",
        "site_id": "site1",
        "collected_fields": fields,
    }
    state.update(extra)
    return state


def _recorder():
    created: list[dict] = []

    def create_fn(*, name: str, trade: str | None, daily_wage) -> None:
        created.append({"name": name, "trade": trade, "daily_wage": daily_wage})

    return created, create_fn


def _answer(workers: list[dict], text: str, *, slot: str = PROMOTION_SLOT, **extra) -> dict:
    fields = {"promotable_workers": workers, "_slot_answer_text": text, **extra}
    return offer_and_promote(_base_state(fields, awaiting_slot=slot))


# ---------------------------------------------------------------------------
# Pass 1 — the offer
# ---------------------------------------------------------------------------


def test_no_promotable_workers_completes_silently():
    """The guard: this workflow is only ever reached with at least one named
    temp worker seeded by the caller. An empty list means the caller made a
    mistake -- bail neutrally rather than sending an empty offer."""
    result = offer_and_promote(_base_state({"promotable_workers": []}))
    assert result["awaiting_slot"] is None
    assert result["pending_prompt"] is None


def test_offer_lists_every_named_worker_with_trade():
    result = offer_and_promote(
        _base_state({"promotable_workers": [AJITH, NIYAS, RAHUL]})
    )

    prompt = result["pending_prompt"]
    assert result["awaiting_slot"] == PROMOTION_SLOT
    assert "Attendance recorded successfully." in prompt
    assert "• Ajith – Mason" in prompt
    assert "• Niyas – Helper" in prompt
    assert "• Rahul – Painter" in prompt


def test_offer_asks_for_names_not_numbers():
    """Numbers are unreadable on a phone once a report has a dozen workers,
    and easy to mis-key. The example is built from the real names on screen."""
    result = offer_and_promote(_base_state({"promotable_workers": [AJITH, RAHUL]}))
    prompt = result["pending_prompt"]

    assert "the names (e.g. Ajith, Rahul)" in prompt
    assert "1." not in prompt
    assert "2." not in prompt


def test_offer_never_carries_a_draft_action():
    """This node only runs after RECORD_LABOUR_ATTENDANCE already confirmed
    and saved -- it must never itself produce something to confirm."""
    result = offer_and_promote(_base_state({"promotable_workers": [AJITH]}))
    assert result.get("draft_action") is None


# ---------------------------------------------------------------------------
# Pass 2 — resolving names
# ---------------------------------------------------------------------------


def test_all_creates_every_worker():
    created, create_fn = _recorder()
    result = _answer([AJITH, NIYAS], "all", _create_worker_fn=create_fn)

    assert [c["name"] for c in created] == ["Ajith", "Niyas"]
    assert "Ajith, Niyas" in result["pending_prompt"]
    assert result["awaiting_slot"] is None


def test_none_creates_nobody_and_says_they_stay_temporary():
    created, create_fn = _recorder()
    result = _answer([AJITH, NIYAS], "none", _create_worker_fn=create_fn)

    assert created == []
    assert "temporary workers" in result["pending_prompt"]
    assert result["awaiting_slot"] is None


def test_selecting_by_name_creates_only_those_named():
    created, create_fn = _recorder()
    _answer([AJITH, NIYAS, RAHUL], "Ajith, Rahul", _create_worker_fn=create_fn)

    assert [c["name"] for c in created] == ["Ajith", "Rahul"]


def test_name_selection_is_case_and_separator_insensitive():
    for reply in ("ajith and rahul", "AJITH, RAHUL", "  ajith   rahul  "):
        created, create_fn = _recorder()
        _answer([AJITH, NIYAS, RAHUL], reply, _create_worker_fn=create_fn)
        assert [c["name"] for c in created] == ["Ajith", "Rahul"], reply


def test_a_multi_word_name_is_matched_as_a_whole():
    ravi_kumar = {"name": "Ravi Kumar", "trade": "mason"}
    created, create_fn = _recorder()
    _answer([ravi_kumar, NIYAS], "Ravi Kumar", _create_worker_fn=create_fn)

    assert [c["name"] for c in created] == ["Ravi Kumar"]


def test_a_name_read_in_capitals_is_selected_by_any_casing():
    """OCR routinely returns attendance sheets in block capitals, so the name
    on the list and the name the supervisor types rarely agree on case."""
    shouty = {"name": "AJITH KUMAR", "trade": "mason"}
    for reply in ("AJITH KUMAR", "ajith kumar", "Ajith Kumar", "  ajith   KUMAR "):
        created, create_fn = _recorder()
        _answer([shouty, NIYAS], reply, _create_worker_fn=create_fn)
        assert [c["name"] for c in created] == ["AJITH KUMAR"], reply


def test_a_first_name_selects_the_one_worker_it_identifies():
    """Typing "Ajith" for a listed "Ajith Kumar" is the natural reply --
    rejecting it made the question feel broken."""
    ajith_kumar = {"name": "Ajith Kumar", "trade": "mason"}
    created, create_fn = _recorder()
    _answer([ajith_kumar, NIYAS], "Ajith", _create_worker_fn=create_fn)

    assert [c["name"] for c in created] == ["Ajith Kumar"]


def test_a_first_name_shared_by_two_listed_workers_re_asks():
    """The guard on the rule above: promoting the wrong person is worse than
    asking twice."""
    created, create_fn = _recorder()
    result = _answer(
        [{"name": "Ajith Kumar"}, {"name": "Ajith Nair"}],
        "Ajith",
        _create_worker_fn=create_fn,
    )

    assert created == []
    assert result["awaiting_slot"] == PROMOTION_SLOT


def test_a_reply_mixing_a_full_name_and_a_first_name_keeps_both():
    """"Ajith and Niyas" matches Niyas in full and Ajith only in part. An
    earlier version stopped at the first pass and silently dropped Ajith."""
    created, create_fn = _recorder()
    _answer(
        [{"name": "Ajith Kumar"}, NIYAS],
        "Ajith and Niyas",
        _create_worker_fn=create_fn,
    )

    assert [c["name"] for c in created] == ["Ajith Kumar", "Niyas"]


def test_the_daily_wage_from_attendance_is_carried_into_the_register():
    created, create_fn = _recorder()
    _answer([AJITH], "Ajith", _create_worker_fn=create_fn)

    assert created[0]["daily_wage"] == "800"
    assert created[0]["trade"] == "mason"


def test_a_reply_naming_nobody_recognisable_re_asks():
    created, create_fn = _recorder()
    result = _answer([AJITH], "Suresh", _create_worker_fn=create_fn)

    assert created == []
    assert result["awaiting_slot"] == PROMOTION_SLOT
    assert "didn't catch that" in result["pending_prompt"]


def test_create_failure_is_reported_not_raised():
    """Attendance is already saved; promotion is a courtesy step and must
    never raise back into the caller."""

    def failing_create(**kwargs):
        raise RuntimeError("boom")

    result = _answer([AJITH], "all", _create_worker_fn=failing_create)
    assert "Could not add" in result["pending_prompt"]
    assert result["awaiting_slot"] is None


def test_missing_create_fn_is_treated_as_failed_not_a_crash():
    result = _answer([AJITH], "all")
    assert "Could not add" in result["pending_prompt"]


# ---------------------------------------------------------------------------
# Duplicate prevention — the point of the whole feature
# ---------------------------------------------------------------------------

REGISTER = [
    {
        "worker_id": "w-existing",
        "name": "Ajith Kumar",
        "trade": "mason",
        "contractor": None,
    }
]


def test_a_likely_existing_worker_is_not_created_without_asking():
    """"Ajith, mason" against registered "Ajith Kumar, mason" -- creating a
    second record here is exactly the duplicate this step exists to stop."""
    created, create_fn = _recorder()
    result = _answer(
        [AJITH], "Ajith", _create_worker_fn=create_fn, _register=REGISTER
    )

    assert created == []
    assert result["awaiting_slot"] == DUPLICATE_SLOT
    assert "similar workers already in your register" in result["pending_prompt"]
    assert "Ajith Kumar" in result["pending_prompt"]


def test_confirming_a_look_alike_is_a_different_person_creates_them():
    created, create_fn = _recorder()
    asked = _answer([AJITH], "Ajith", _create_worker_fn=create_fn, _register=REGISTER)

    resumed = offer_and_promote(
        _base_state(
            {**asked["collected_fields"], "_slot_answer_text": "Ajith"},
            awaiting_slot=DUPLICATE_SLOT,
        )
    )

    assert [c["name"] for c in created] == ["Ajith"]
    assert "Added to your Worker Register: Ajith" in resumed["pending_prompt"]
    assert resumed["awaiting_slot"] is None


def test_saying_none_to_the_duplicate_question_creates_nobody():
    created, create_fn = _recorder()
    asked = _answer([AJITH], "Ajith", _create_worker_fn=create_fn, _register=REGISTER)

    resumed = offer_and_promote(
        _base_state(
            {**asked["collected_fields"], "_slot_answer_text": "none"},
            awaiting_slot=DUPLICATE_SLOT,
        )
    )

    assert created == []
    assert resumed["awaiting_slot"] is None


def test_unambiguous_workers_are_created_immediately_alongside_a_held_one():
    """A mixed batch must not punish the clean names: they are written on the
    spot, and only the look-alike waits for an answer. The closing summary
    then covers both halves at once."""
    created, create_fn = _recorder()
    asked = _answer(
        [AJITH, RAHUL], "all", _create_worker_fn=create_fn, _register=REGISTER
    )

    assert [c["name"] for c in created] == ["Rahul"]
    assert asked["awaiting_slot"] == DUPLICATE_SLOT

    resumed = offer_and_promote(
        _base_state(
            {**asked["collected_fields"], "_slot_answer_text": "Ajith"},
            awaiting_slot=DUPLICATE_SLOT,
        )
    )

    assert [c["name"] for c in created] == ["Rahul", "Ajith"]
    assert "Rahul" in resumed["pending_prompt"]
    assert "Ajith" in resumed["pending_prompt"]


def test_an_empty_register_never_triggers_the_duplicate_question():
    """Day one: nobody is registered, so every named worker is genuinely new
    and the extra question would be pure friction."""
    created, create_fn = _recorder()
    result = _answer([AJITH], "all", _create_worker_fn=create_fn, _register=[])

    assert [c["name"] for c in created] == ["Ajith"]
    assert result["awaiting_slot"] is None


def test_a_different_trade_still_asks_rather_than_assuming_a_new_person():
    """"Ajith, painter" vs registered "Ajith Kumar, mason": people do change
    trade, so this is a question, not a silent second record.

    This is the case matching.ASK misses -- the trade penalty drags a real
    partial-name signal under the attendance threshold. Promotion screens at
    a lower bar precisely so it lands here instead (see _DUPLICATE_SUSPICION).
    """
    created, create_fn = _recorder()
    result = _answer(
        [{"name": "Ajith", "trade": "painter"}],
        "Ajith",
        _create_worker_fn=create_fn,
        _register=REGISTER,
    )

    assert created == []
    assert result["awaiting_slot"] == DUPLICATE_SLOT


def test_a_genuinely_different_name_is_created_with_no_extra_question():
    """The other half of the trade-off: the duplicate screen must not turn
    every promotion into an interrogation. A name sharing nothing with any
    register entry is written straight away, however much else matches."""
    created, create_fn = _recorder()
    result = _answer(
        [{"name": "Niyas", "trade": "mason"}],
        "Niyas",
        _create_worker_fn=create_fn,
        _register=REGISTER,
    )

    assert [c["name"] for c in created] == ["Niyas"]
    assert result["awaiting_slot"] is None
