"""Worker promotion workflow node — unit tests (pure function, no LangGraph needed).

Mirrors tests/unit/test_labour_update_nodes.py's style: the node is re-entrant
and has no memory between passes, so tests spanning two messages thread
`collected_fields` and `awaiting_slot` through by hand, exactly as
WorkflowRuntime.provide_input does.
"""

from __future__ import annotations

from workflows.worker_promotion.nodes import PROMOTION_SLOT, offer_and_promote

RAVI = {"name": "Ravi", "trade": "mason", "daily_wage": "800"}
ARUN = {"name": "Arun", "trade": "painter", "daily_wage": "700"}


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


# ---------------------------------------------------------------------------
# Pass 1 — building the offer
# ---------------------------------------------------------------------------


def test_no_promotable_workers_completes_silently():
    """The assertion guard: this workflow is only ever reached with at least
    one named temp worker seeded by the caller. An empty list means the
    caller made a mistake -- bail neutrally rather than sending a broken
    offer with no names in it."""
    result = offer_and_promote(_base_state({"promotable_workers": []}))
    assert result["awaiting_slot"] is None
    assert result["pending_prompt"] is None


def test_offer_lists_every_named_worker_with_trade():
    result = offer_and_promote(_base_state({"promotable_workers": [RAVI, ARUN]}))

    assert result["awaiting_slot"] == PROMOTION_SLOT
    assert "Ravi (mason)" in result["pending_prompt"]
    assert "Arun (painter)" in result["pending_prompt"]


def test_offer_never_interrupts_the_confirmation_experience():
    """This node only ever runs after RECORD_LABOUR_ATTENDANCE has already
    confirmed and saved -- it must never itself carry a draft_action, only a
    slot question."""
    result = offer_and_promote(_base_state({"promotable_workers": [RAVI]}))
    assert "draft_action" not in result or result.get("draft_action") is None


# ---------------------------------------------------------------------------
# Pass 2 — parsing the answer
# ---------------------------------------------------------------------------


def _answer(workers: list[dict], text: str, **extra) -> dict:
    fields = {"promotable_workers": workers, "_slot_answer_text": text, **extra}
    return offer_and_promote(
        _base_state(fields, awaiting_slot=PROMOTION_SLOT)
    )


def test_all_creates_every_worker():
    created: list[str] = []

    def create_fn(*, name: str, trade: str | None, daily_wage) -> None:
        created.append(name)

    result = _answer([RAVI, ARUN], "all", _create_worker_fn=create_fn)

    assert created == ["Ravi", "Arun"]
    assert "Ravi" in result["pending_prompt"]
    assert "Arun" in result["pending_prompt"]
    assert result["awaiting_slot"] is None


def test_none_creates_nobody_and_says_so():
    created: list[str] = []

    def create_fn(**kwargs) -> None:
        created.append(kwargs["name"])

    result = _answer([RAVI, ARUN], "none", _create_worker_fn=create_fn)

    assert created == []
    assert "temporary workers" in result["pending_prompt"]


def test_quick_action_button_labels_are_recognised():
    """Quick-action taps come back as the button label text, not a sentinel
    value -- the node must recognise "All"/"None" case-insensitively."""
    created: list[str] = []
    result = _answer(
        [RAVI], "All", _create_worker_fn=lambda **kw: created.append(kw["name"])
    )
    assert created == ["Ravi"]
    assert result["awaiting_slot"] is None


def test_numeric_selection_creates_only_the_chosen_ones():
    created: list[str] = []
    result = _answer(
        [RAVI, ARUN], "1", _create_worker_fn=lambda **kw: created.append(kw["name"])
    )
    assert created == ["Ravi"]
    assert result["awaiting_slot"] is None


def test_comma_and_space_separated_numbers_both_work():
    created: list[str] = []
    _answer(
        [RAVI, ARUN], "1, 2", _create_worker_fn=lambda **kw: created.append(kw["name"])
    )
    assert created == ["Ravi", "Arun"]

    created2: list[str] = []
    _answer(
        [RAVI, ARUN], "1 2", _create_worker_fn=lambda **kw: created2.append(kw["name"])
    )
    assert created2 == ["Ravi", "Arun"]


def test_out_of_range_number_alone_re_asks():
    result = _answer([RAVI], "99", _create_worker_fn=lambda **kw: None)
    assert result["awaiting_slot"] == PROMOTION_SLOT
    assert "didn't catch that" in result["pending_prompt"]


def test_unintelligible_reply_re_asks_rather_than_guessing():
    result = _answer([RAVI], "maybe later idk", _create_worker_fn=lambda **kw: None)
    assert result["awaiting_slot"] == PROMOTION_SLOT


def test_duplicate_guard_skips_a_worker_already_in_the_register():
    """Final duplicate guard: if the worker was matched to an existing
    register entry between the offer being sent and answered (a race, or the
    caller passed a matched_worker_id), the write is skipped rather than
    creating a second record."""
    matched = {**RAVI, "matched_worker_id": "existing-id"}
    created: list[str] = []
    result = _answer(
        [matched],
        "1",
        _create_worker_fn=lambda **kw: created.append(kw["name"]),
        _existing_worker_ids=["existing-id"],
    )
    assert created == []
    assert "Could not add" in result["pending_prompt"]


def test_create_failure_is_reported_not_raised():
    """A DB write failure during promotion must never raise back into the
    caller -- attendance is already saved; promotion is a courtesy step."""

    def failing_create(**kwargs):
        raise RuntimeError("boom")

    result = _answer([RAVI], "1", _create_worker_fn=failing_create)
    assert "Could not add" in result["pending_prompt"]
    assert result["awaiting_slot"] is None


def test_missing_create_fn_is_treated_as_skipped_not_a_crash():
    result = _answer([RAVI], "1")
    assert "Could not add" in result["pending_prompt"]
