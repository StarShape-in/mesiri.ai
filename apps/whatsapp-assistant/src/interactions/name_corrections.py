"""Parsing "Akhil -> Akhilesh" out of a reply. Pure, no AI, no I/O.

OCR and speech will never read every attendance sheet perfectly, and a
supervisor who spots two wrong names in the preview should be able to fix
them in one message rather than restarting the report.

Deterministic on purpose, not classified by the LLM. The shape is
unambiguous -- a separator with a name either side -- so the same "a plain
reply costs no tokens" principle that governs the confirmation fast path
applies here (see interactions/handler.py's handle_fast_path). It also makes
the behaviour reproducible: the same message always parses the same way,
which matters for something that edits who gets paid.

Deliberately NOT accepted as a separator:

``:``  "Note: Akhil worked late" is a sentence, not a correction, and colons
       turn up constantly in dictated notes.
``-``  a lone hyphen appears inside real names ("Ravi-Kumar") and in list
       bullets. Only the arrow forms ``->`` / ``-->`` / ``→`` count.
"""

from __future__ import annotations

import re

#: old -> new, old => new, old → new, old = new, and the spoken forms
#: "old is new" / "old should be new" / "old not new". Arrows are awkward to
#: type on a phone keyboard, and "Akhil is Akhilesh" is what people actually
#: write -- but a word separator matches far more loosely than an arrow, so
#: everything it produces is checked against the names actually on the
#: preview before being applied (see `keep_reported_names`).
_PAIR = re.compile(
    r"^\s*(?P<old>.+?)\s*"
    r"(?:-{1,2}>|=>|→|=|\bshould\s+be\b|\bis\s+actually\b|\bis\b|\bnot\b)"
    r"\s*(?P<new>.+?)\s*$",
    re.I,
)

#: A leading label the user may type above the pairs ("Correct:", "Fix:").
#: Stripped so it is not mistaken for the first correction.
_HEADER = re.compile(r"^\s*(correct|correction|corrections|fix|change)\s*:?\s*$", re.I)

#: Names are short. Anything longer is a sentence that happens to contain an
#: arrow, and treating it as a name would put a paragraph in the register.
_MAX_NAME_LENGTH = 60


def parse_name_corrections(text: str) -> dict[str, str]:
    """Return {old_name: new_name} for every correction found in ``text``.

    Empty when the reply contains none, which is the signal to treat the
    message as something else entirely -- this must never claim a reply it
    does not clearly own.

    Accepts one per line, or several separated by commas or semicolons, so
    all of these work:

        Correct:
        Akhil -> Akhilesh
        Niyas -> Niyas PM

        Akhil=Akhilesh, Niyas=Niyas PM
    """
    if not text or not text.strip():
        return {}

    # Split on newlines first, then on , and ; -- a name never contains
    # either, so this cannot break a legitimate one apart.
    fragments: list[str] = []
    for line in text.splitlines():
        fragments.extend(re.split(r"[,;]", line))

    corrections: dict[str, str] = {}
    for fragment in fragments:
        if not fragment.strip() or _HEADER.match(fragment):
            continue
        match = _PAIR.match(fragment)
        if match is None:
            continue
        old = match.group("old").strip().strip("•-*").strip()
        new = match.group("new").strip()
        if not old or not new:
            continue
        if len(old) > _MAX_NAME_LENGTH or len(new) > _MAX_NAME_LENGTH:
            continue
        if old.casefold() == new.casefold():
            continue  # a no-op correction is noise, not an instruction
        corrections[old] = new

    return corrections


def keep_reported_names(
    corrections: dict[str, str], reported_names: list[str]
) -> dict[str, str]:
    """Drop corrections whose left side isn't a name on the current preview.

    This is what makes the word separators safe to accept. "Ravi is mason"
    parses as a pair, but it is a description of Ravi, not a rename -- and
    with a bare arrow-only parser the same sentence typed as "Ravi - mason"
    would too. Rather than guess from the wording, the left side is required
    to be a worker actually in the report being confirmed, and the right side
    is required not to be a trade.

    A reply containing no correction the preview recognises returns empty,
    which sends the message back down the normal path -- so an unrelated
    sentence is never mistaken for an edit to somebody's name.
    """
    from mesiri.domains.workforce.workers import normalize_name, normalize_trade

    known = {normalize_name(n) for n in reported_names if n}
    if not known:
        return {}

    trades = _known_trade_words()
    kept: dict[str, str] = {}
    for old, new in corrections.items():
        if normalize_name(old) not in known:
            continue
        # "Ravi is mason" states a trade, and a worker whose recorded name
        # becomes "mason" is unrecoverable from WhatsApp.
        if normalize_trade(new) in trades:
            continue
        kept[old] = new
    return kept


def _known_trade_words() -> set[str]:
    """Every recognised trade, normalized. Read from the domain vocabulary so
    a trade added there is automatically rejected as a name here."""
    from mesiri.domains.workforce.workers import _TRADE_SYNONYMS

    return set(_TRADE_SYNONYMS) | set(_TRADE_SYNONYMS.values())
