"""workflows.who_am_i.classifier -- deterministic who-am-i detection.

Pins the matching behavior directly since interactions/handler.py's
handle_whoami_trigger depends on it staying deterministic (whole-phrase
match, not substring), same reasoning as test_greeting_classifier.py.
"""

from __future__ import annotations

import pytest

from workflows.who_am_i.classifier import is_whoami_trigger


@pytest.mark.parametrize(
    "text",
    [
        "who am i",
        "Who Am I",
        "WHOAMI",
        "who am i talking to",
        "who is this",
        "my profile",
        "my details",
        "which company am i in",
        "which site am i on",
        "my site",
    ],
)
def test_recognizes_configured_whoami_phrases_case_insensitively(text):
    assert is_whoami_trigger(text) is True


def test_does_not_match_a_real_material_report():
    assert is_whoami_trigger("50 bags of cement arrived") is False


def test_does_not_match_phrase_mentioned_in_passing():
    """Whole-message match, not "contains" -- mentioning "who am i" inside a
    longer real report must not swallow it as an identity lookup."""
    assert is_whoami_trigger("who am i to say no, but 50 bags of cement arrived") is False


@pytest.mark.parametrize("text", [None, "", "   "])
def test_empty_or_none_is_not_a_whoami_trigger(text):
    assert is_whoami_trigger(text) is False


@pytest.mark.parametrize("text", ["who am i?", "  whoami  ", "My Profile."])
def test_punctuation_and_whitespace_are_tolerated(text):
    assert is_whoami_trigger(text) is True
