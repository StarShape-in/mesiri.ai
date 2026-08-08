"""Near-match scoring for entities whose names are *written by people* --
users, vendors, and anything else Phase 4 migrates that has no searchable
structure to lean on.

Extracted from member_resolution.py when VENDOR became the second caller
(ENTITY_RESOLUTION_PLAN.md §5, Phase 4). Nothing about the scoring was ever
user-specific: `resolve_name_hint` already took (entity_id, display_name)
pairs and knew nothing about users. Phase 3 established that this layer is
two halves -- a matching half and a vocabulary half -- and this module is the
matching half for the person-like entities. Catalog-like entities
(materials, where matching happens in SQL) use only the vocabulary; see
material_resolution.py.

## Why this uses real near-match scoring, unlike workforce/matching.py

`match_worker`'s docstring is explicit and deliberate: *"Deliberately not
using fuzzy string distance... one character often *is* the difference
between two people (Sunil/Sunita, Ramesh/Rakesh), and a near-miss that
scores highly is exactly how a false merge happens."* That module is
right, and this one does not contradict it -- the two problems differ in
the one dimension that matters:

- `match_worker` scores a whole ATTENDANCE SHEET (tens of names) against a
  register, unattended -- AUTO_ACCEPT silently commits a match with nobody
  watching, so a false-positive fuzzy match becomes a silently-merged wrong
  person, discovered (if ever) long after the fact.
- This module scores ONE name, once, always followed by a tappable picker
  with an explicit escape row (Ambiguous, never Resolved, for anything short
  of an exact match). Nothing here is ever silently accepted. The failure
  mode `match_worker` was rewritten to avoid -- a false merge nobody
  notices -- cannot happen through this path, because the human who sent the
  message is the one confirming the match, in the same conversation, seconds
  later.

Where the two modules agree completely: neither ever guesses silently.
`score_candidate` (kept in workforce/matching.py "for when smarter matching
comes back") is the closer relative of what this module does -- a
single-candidate, human-confirmed question -- than `match_worker`'s bulk
all-or-nothing rule.

Uses stdlib `difflib.SequenceMatcher` rather than a new dependency
(rapidfuzz/jellyfish are not in this project's dependency tree, and pulling
one in for a single-field, human-confirmed comparison is not worth the new
dependency).
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from runtime.entity_resolution import normalize_name
from workflows.entities import Ambiguous, Candidate, Missing, ResolutionOutcome, Resolved

#: Below this, two names are treated as sharing nothing -- silence, not a
#: candidate. Conservative on purpose: a stray low-similarity row in the
#: picker is worse than a Missing that offers to create instead (ADR-E4:
#: Missing always offers, never dead-ends).
_ASK_THRESHOLD = 0.6

#: There is deliberately no auto-match band above this: an earlier draft
#: silently resolved anything scoring above ~0.97 as "close enough,"
#: reasoning that whitespace/punctuation noise was all that was left uncaught
#: by the exact-match probe above. Measurement showed real near-miss pairs
#: (Sunil/Sunill, a doubled letter) score in the same 0.9+ band as genuine
#: punctuation noise, with no clean line between them -- exactly the
#: silent-false-merge failure mode match_worker's docstring documents and
#: rewrote itself to avoid. Anything short of a byte-identical
#: (post-normalization) match is Ambiguous, full stop; the cost is one
#: extra tap on a trailing-period typo, which is cheap, against a silent
#: wrong-person merge, which is not.

#: How many near-matches to offer at once. A WhatsApp list caps at 10 rows;
#: showing that many low-confidence guesses reads as "the assistant has no
#: idea", so this stays well under the transport limit.
_MAX_CANDIDATES = 5


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(a=a, b=b).ratio()


def _names_a_whole_word_of(hint: str, display_name: str) -> bool:
    """Whether ``hint`` is exactly one of ``display_name``'s words.

    People refer to each other by first name -- "remind Ilan every Monday",
    "give Rajesh 2000" -- while the roster stores full names. Pure ratio
    scoring handles that only by accident, and badly: it depends on the
    length of the part left over, so "Rajesh"/"Rajesh Kumar" clears 0.6
    (0.667) while "Ilan"/"Ilan Usman" does not (0.571) and came back Missing
    -- "I couldn't find Ilan" about someone plainly in the org. A shorter
    first name was simply likelier to fail, which is not a rule anyone could
    have predicted or worked around.

    Deliberately a candidate signal only, never a resolve: an org can easily
    hold two people sharing a first name, so this always ends in the picker
    the caller was going to show anyway. Whole words only -- a substring test
    would make "an" match "Anand".
    """
    return normalize_name(hint) in normalize_name(display_name).split()


@dataclass(frozen=True, slots=True)
class NamedCandidate:
    """One active row, as the pure scorer needs to see it -- id and display
    name only, so this module has no dependency on the backend's UserSummary
    or Vendor and can be unit-tested with plain tuples."""

    entity_id: str
    display_name: str


def resolve_name_hint(name_hint: str, candidates: list[NamedCandidate]) -> ResolutionOutcome:
    """Pure: score ``name_hint`` against every active ``candidates`` row.

    An exact (case-insensitive, whitespace-normalized) match wins outright,
    mirroring materials' find_materials ("an exact match always wins outright
    and is returned alone"). Short of that, every candidate scoring at or
    above _ASK_THRESHOLD is offered, best first, capped at _MAX_CANDIDATES;
    below that threshold, nothing is close enough to mention at all.
    """
    hint = normalize_name(name_hint)
    if not hint:
        return Missing(name_hint=name_hint)

    for candidate in candidates:
        if normalize_name(candidate.display_name) == hint:
            return Resolved(entity_id=candidate.entity_id, display_name=candidate.display_name)

    scored = sorted(
        ((_similarity(hint, normalize_name(c.display_name)), c) for c in candidates),
        key=lambda pair: pair[0],
        reverse=True,
    )

    offered = [
        (score, c)
        for score, c in scored
        if score >= _ASK_THRESHOLD or _names_a_whole_word_of(hint, c.display_name)
    ]
    if not offered:
        return Missing(name_hint=name_hint)

    return Ambiguous(
        candidates=tuple(
            Candidate(entity_id=c.entity_id, display_name=c.display_name)
            for _, c in offered[:_MAX_CANDIDATES]
        )
    )
