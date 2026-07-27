"""mesiri_ai.undo_classifier -- deterministic undo-intent detection (#6 Undo).

Pins the matching behavior since runtime/dependencies.py depends on it
staying deterministic (whole-phrase match, not substring) -- same reasoning
as test_whoami_classifier.py.
"""

from __future__ import annotations

import pytest

from mesiri_ai.undo_classifier import UNDO_SEMANTIC_HINT, is_undo_trigger


@pytest.mark.parametrize(
    "text",
    [
        "undo",
        "Undo That",
        "UNDO IT",
        "delete that",
        "delete it",
        "cancel that",
        "remove that",
        "scrap that",
        "ignore that",
        "ignore my last message",
        "ignore previous message",
        "that was wrong",
        "that's wrong",
        "wrong entry",
        "reverse that",
    ],
)
def test_recognizes_configured_undo_phrases_case_insensitively(text):
    assert is_undo_trigger(text) is True


def test_does_not_match_a_real_material_report():
    assert is_undo_trigger("50 bags of cement arrived") is False


def test_does_not_match_phrase_mentioned_in_passing():
    """Whole-message match, not "contains" -- mentioning "undo" inside a
    longer real report must not swallow it as an undo request."""
    assert is_undo_trigger("undo that, and also record 40 bags of cement") is False


@pytest.mark.parametrize("text", [None, "", "   "])
def test_empty_or_none_is_not_an_undo_trigger(text):
    assert is_undo_trigger(text) is False


@pytest.mark.parametrize("text", ["undo?", "  delete that  ", "That Was Wrong."])
def test_punctuation_and_whitespace_are_tolerated(text):
    assert is_undo_trigger(text) is True


def test_semantic_hint_constant_is_reversal():
    # Threaded into process_inbound_message(semantic_hint=...) to bias
    # extraction toward SemanticType.REVERSAL -- pinned so a rename doesn't
    # silently break the runtime/dependencies.py wiring.
    assert UNDO_SEMANTIC_HINT == "reversal"
