"""Deterministic detection of a greeting/menu trigger ("hi", "menu", "help"...).

Lives in mesiri_ai (not interactions/) specifically so understanding/pipeline.py
can use it too: understanding/ must not import from interactions/ (dependency
direction -- ingress -> understanding -> context -> planner -> workflows ->
interactions, no stage may depend on a later one), but any module may import
mesiri_ai, matching the existing precedent of mesiri_ai.confidence.
ConfidencePolicy (deterministic, no AI SDK, already used the same way).

Vocabulary lives in greeting_phrases.json -- a config edit, not a code change.

Matching is deliberately stricter than confirmation_phrases.json's classifier:
that one only checks for a *contained* token, which is fine there because it
only ever runs while a specific workflow is already pending (a false positive
is contained). This one runs unconditionally on every message, so "contains a
greeting word" is not enough -- "50 bags of cement arrived, hi there" must not
skip extraction just because it contains "hi". Every token in the message must
itself be a recognized greeting word, i.e. the whole message is a greeting and
nothing else. No LLM -- a greeting must never depend on AI classification
correctly guessing that "hi" carries no business fields.
"""

from __future__ import annotations

import json
import pathlib
import string

_PHRASES_PATH = pathlib.Path(__file__).with_name("greeting_phrases.json")
_PUNCTUATION = string.punctuation


def _load_phrases() -> set[str]:
    data = json.loads(_PHRASES_PATH.read_text(encoding="utf-8"))
    return {p.casefold() for p in data.get("greeting", [])}


# Loaded once at import — the JSON is static configuration.
_GREETING_PHRASES = _load_phrases()


def is_greeting_trigger(text: str | None) -> bool:
    """True if `text` is *entirely* greeting words, nothing else.

    Applied to whatever text is available -- typed directly, or the
    transcript/translation after voice STT -- so "hi" is recognized the
    same way regardless of how it arrived (see understanding/pipeline.py's
    _handle_text/_handle_voice, and interactions/handler.py's pre-pipeline
    fast path for the text case).
    """
    if not text or not text.strip():
        return False
    # Strip trailing/leading punctuation per token -- "Hi!" and "hello." are
    # far more common for a greeting than for a confirmation reply, so unlike
    # confirmation_phrases.json's classifier this needs to tolerate it.
    tokens = [t.strip(_PUNCTUATION) for t in text.strip().casefold().split()]
    tokens = [t for t in tokens if t]
    return bool(tokens) and all(token in _GREETING_PHRASES for token in tokens)
