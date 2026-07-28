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

#: old -> new, old => new, old → new, old = new. The separator must be one of
#: these exactly; see the module docstring for what is excluded and why.
_PAIR = re.compile(
    r"^\s*(?P<old>.+?)\s*(?:-{1,2}>|=>|→|=)\s*(?P<new>.+?)\s*$",
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
