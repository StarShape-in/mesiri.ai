"""Deterministic detection of an "undo" trigger (#6 Undo).

Mirrors whoami_classifier.py exactly -- same whole-message, whole-phrase
match, same reasoning ("a plain undo request costs no tokens"), same
"vocabulary lives in JSON, not code" convention. Lives in mesiri_ai for the
same dependency-direction reason whoami_classifier does: any module may
import mesiri_ai, but understanding/ must not import from workflows/ or
interactions/.

Unlike who-am-i, this classifier does NOT produce a reply by itself -- undo
is a mutating action and must go through the normal confirm/execute
machinery (single-active invariant, optimistic locking, real domain
reversal). Its only job is to recognize the INTENT ("the user wants to undo
something") deterministically; interactions/handler.py uses that to bias
extraction toward SemanticType.REVERSAL via the existing semantic_hint
mechanism (the same one category_hint.py already uses for the
post-inventory-query material bias) -- WHICH thing gets undone is then
resolved by runtime.reversal_query.find_latest_of_either_kind, at seeding
time, same as every other workflow's "a node must never query a repository
itself" seeding step.
"""

from __future__ import annotations

import json
import pathlib
import string

_PHRASES_PATH = pathlib.Path(__file__).with_name("undo_phrases.json")
_PUNCTUATION_TABLE = str.maketrans("", "", string.punctuation)

#: The semantic_hint value that biases extraction toward REVERSAL -- passed
#: as `process_inbound_message(semantic_hint=...)`, same parameter every
#: other hint (category tap, image purpose) already uses.
UNDO_SEMANTIC_HINT = "reversal"


def _normalize(text: str) -> str:
    text = text.strip().casefold().translate(_PUNCTUATION_TABLE)
    return " ".join(text.split())


def _load_phrases() -> set[str]:
    # Punctuation-stripped at load time too, not just on the incoming
    # message -- "that's wrong" in the JSON must match after the SAME
    # normalization _normalize() above applies to the message, or an
    # apostrophe'd phrase in the vocabulary would silently never match.
    data = json.loads(_PHRASES_PATH.read_text(encoding="utf-8"))
    return {_normalize(p) for p in data.get("undo", [])}


# Loaded once at import -- the JSON is static configuration.
_UNDO_PHRASES = _load_phrases()


def is_undo_trigger(text: str | None) -> bool:
    """True if `text` is *entirely* one of the recognized undo phrasings.

    Whole-message match (not "contains") -- "undo that, and also record 40
    bags of cement" must not skip normal extraction just because it mentions
    "undo" in passing.
    """
    if not text or not text.strip():
        return False
    return _normalize(text) in _UNDO_PHRASES
