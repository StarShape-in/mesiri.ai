"""Deterministic detection of a "who am I" / identity-lookup trigger.

A site engineer asking "who am i" (or "whoami", "my profile", "which
company/site am i on", ...) should get their identity summary -- name, role,
organization, projects, sites -- without ever going through the AI pipeline,
same principle as mesiri_ai.greeting_classifier ("a plain identity question
costs no tokens"). Kept as its own module/folder (rather than folded into the
greeting classifier) because building the actual reply needs the caller's
resolved ActorIdentity, not just a phrase match -- see
interactions.handler.InteractionHandler.handle_whoami_trigger and
context.live_identity.whoami_reply.

Vocabulary lives in phrases.json -- a config edit, not a code change.

Unlike greeting_classifier's per-token match (fine there because every
greeting word IS the whole message space), these are multi-word phrases --
"who am i" is only meaningful as a phrase, not as three independently
meaningful tokens -- so matching is whole-message-equals-one-of-these-phrases
(punctuation stripped, whitespace collapsed, case-folded), not per-token.
"""

from __future__ import annotations

import json
import pathlib
import string

_PHRASES_PATH = pathlib.Path(__file__).with_name("phrases.json")
_PUNCTUATION_TABLE = str.maketrans("", "", string.punctuation)


def _load_phrases() -> set[str]:
    data = json.loads(_PHRASES_PATH.read_text(encoding="utf-8"))
    return {p.casefold() for p in data.get("whoami", [])}


# Loaded once at import -- the JSON is static configuration.
_WHOAMI_PHRASES = _load_phrases()


def _normalize(text: str) -> str:
    text = text.strip().casefold().translate(_PUNCTUATION_TABLE)
    return " ".join(text.split())


def is_whoami_trigger(text: str | None) -> bool:
    """True if `text` is *entirely* one of the recognized who-am-i phrasings.

    Whole-message match (not "contains") -- "who am i, and also 50 bags of
    cement arrived" must not skip extraction just because it mentions "who am
    i" in passing.
    """
    if not text or not text.strip():
        return False
    return _normalize(text) in _WHOAMI_PHRASES
