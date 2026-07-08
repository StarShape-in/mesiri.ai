"""Deterministic reply classifier — unit tests (English/Malayalam/emoji + config extensibility)."""

from __future__ import annotations

import pytest

from interactions.intent import InteractionIntent

CONFIRM = InteractionIntent.CONFIRM
REJECT = InteractionIntent.REJECT
CANCEL = InteractionIntent.CANCEL
UNRELATED = InteractionIntent.UNRELATED
AMBIGUOUS = InteractionIntent.AMBIGUOUS


@pytest.mark.parametrize(
    "text,expected",
    [
        ("yes", CONFIRM),
        ("Yes", CONFIRM),
        ("YES please", CONFIRM),
        ("y", CONFIRM),
        ("ok", CONFIRM),
        ("confirm", CONFIRM),
        ("👍", CONFIRM),
        ("ശരി", CONFIRM),  # Malayalam "ok"
        ("athe", CONFIRM),  # transliteration of "yes"
        ("no", REJECT),
        ("nope", REJECT),
        ("wrong", REJECT),
        ("അല്ല", REJECT),  # Malayalam "no"
        ("cancel", CANCEL),
        ("stop it", CANCEL),
        ("never mind", CANCEL),
        ("venda", CANCEL),  # transliteration of "don't want"
        ("yes no", AMBIGUOUS),  # confirm + negative
        ("5 bags cement arrived at site A", UNRELATED),
        ("what is the total so far?", UNRELATED),
        ("", UNRELATED),
        ("   ", UNRELATED),
        (None, UNRELATED),
    ],
)
def test_classify_reply(text, expected):
    from interactions.classifier import classify_reply

    assert classify_reply(text) is expected


def test_no_is_not_matched_inside_now():
    """Single-token matching: 'no' must not fire on 'now' / substrings."""
    from interactions.classifier import classify_reply

    assert classify_reply("now recording") is UNRELATED


def test_phrase_sets_are_loaded_from_json_config():
    """The vocabulary is data, not code: the loader reads the shipped JSON and
    it already carries multiple languages (so adding one is a config edit)."""
    import json
    import pathlib

    import interactions.classifier as classifier_module

    path = pathlib.Path(classifier_module.__file__).with_name("confirmation_phrases.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert {"confirm", "reject", "cancel"} <= set(raw)
    # Malayalam present alongside English → language is configuration.
    assert "ശരി" in raw["confirm"]

    loaded = classifier_module._load_phrase_sets()
    assert "yes" in loaded["confirm"]  # casefolded, ready for matching


def test_adding_a_phrase_classifies_without_touching_logic(monkeypatch):
    """Injecting a new word into the loaded phrase sets is enough — no code edit
    to classify_reply. 'haan' (Hindi yes) is deliberately not in the shipped set."""
    import interactions.classifier as classifier_module

    assert classifier_module.classify_reply("haan") is UNRELATED  # not shipped yet

    extended = {
        "confirm": [*classifier_module._PHRASE_SETS["confirm"], "haan"],
        "reject": classifier_module._PHRASE_SETS["reject"],
        "cancel": classifier_module._PHRASE_SETS["cancel"],
    }
    monkeypatch.setattr(classifier_module, "_PHRASE_SETS", extended)
    assert classifier_module.classify_reply("haan") is InteractionIntent.CONFIRM
