"""workflows/slots.py — unit tests (pure, no LangGraph, no I/O)."""

from __future__ import annotations

import pytest

from workflows.slots import SlotCandidate, match_slot_answer, resolve_single_choice_slot


def test_zero_candidates_resolves_unset():
    resolution = resolve_single_choice_slot(slot_name="account_id", prompt_title="Which?", candidates=[])
    assert resolution.resolved_value is None
    assert resolution.awaiting_slot is None
    assert resolution.slot_prompt is None


def test_one_candidate_autofills_silently():
    resolution = resolve_single_choice_slot(
        slot_name="account_id", prompt_title="Which?", candidates=[SlotCandidate("a1", "Cash")]
    )
    assert resolution.resolved_value == "a1"
    assert resolution.awaiting_slot is None
    assert resolution.slot_prompt is None


def test_multiple_candidates_asks_with_numbered_prompt():
    resolution = resolve_single_choice_slot(
        slot_name="account_id",
        prompt_title="Which account?",
        candidates=[SlotCandidate("a1", "Cash"), SlotCandidate("a2", "Bank")],
    )
    assert resolution.resolved_value is None
    assert resolution.awaiting_slot == "account_id"
    assert "1. Cash" in resolution.slot_prompt
    assert "2. Bank" in resolution.slot_prompt
    assert "Which account?" in resolution.slot_prompt


def test_slot_resolution_rejects_awaiting_slot_without_prompt():
    from workflows.slots import SlotResolution

    with pytest.raises(ValueError):
        SlotResolution(resolved_value=None, awaiting_slot="account_id", slot_prompt=None)


def test_slot_resolution_rejects_both_resolved_and_awaiting():
    from workflows.slots import SlotResolution

    with pytest.raises(ValueError):
        SlotResolution(resolved_value="a1", awaiting_slot="account_id", slot_prompt="Which?")


_CANDIDATES = [SlotCandidate("a1", "Site Cash"), SlotCandidate("a2", "Company Bank")]


def test_match_numbered_reply():
    assert match_slot_answer("1", _CANDIDATES) == "a1"
    assert match_slot_answer("2", _CANDIDATES) == "a2"


def test_match_numbered_reply_out_of_range_returns_none():
    assert match_slot_answer("5", _CANDIDATES) is None
    assert match_slot_answer("0", _CANDIDATES) is None


def test_match_exact_label_case_insensitive():
    assert match_slot_answer("site cash", _CANDIDATES) == "a1"
    assert match_slot_answer("SITE CASH", _CANDIDATES) == "a1"


def test_match_substring_reply():
    assert match_slot_answer("pay from Company Bank please", _CANDIDATES) == "a2"


def test_match_no_match_returns_none():
    assert match_slot_answer("purple monkey dishwasher", _CANDIDATES) is None


def test_match_blank_reply_returns_none():
    assert match_slot_answer("   ", _CANDIDATES) is None
