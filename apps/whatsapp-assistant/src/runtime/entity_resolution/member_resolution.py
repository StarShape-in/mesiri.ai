"""Resolve a project-member name hint ("Hysam") against an org's active
users -- the fix for the live bug in ENTITY_RESOLUTION_PLAN.md §1: a
Malayalam message named a real person (ഹൈസം, transliterated "Hysam") who
existed in the org as "Hisham", and the assistant's only lookup
(PostgresUserRepository.find_by_full_name_active) is an exact
case-insensitive match -- so every retry failed identically, forever.

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
  with an explicit "Someone else" escape hatch (Ambiguous, never Resolved,
  for anything short of an exact match). Nothing here is ever silently
  accepted. The failure mode `match_worker` was rewritten to avoid --
  a false merge nobody notices -- cannot happen through this path, because
  the human who sent the message is the one confirming the match, in the
  same conversation, seconds later.

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
from typing import TYPE_CHECKING

from workflows.entities import Ambiguous, Candidate, Missing, ResolutionOutcome, Resolved

if TYPE_CHECKING:
    from mesiri.infrastructure.postgres.database import PostgresDatabase

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


def _normalize(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(a=a, b=b).ratio()


@dataclass(frozen=True, slots=True)
class NamedCandidate:
    """One active user, as the pure scorer needs to see it -- id and display
    name only, so this module has no dependency on the backend's
    UserSummary and can be unit-tested with plain tuples."""

    entity_id: str
    display_name: str


def resolve_name_hint(
    name_hint: str, candidates: list[NamedCandidate]
) -> ResolutionOutcome:
    """Pure: score ``name_hint`` against every active ``candidates`` row.

    An exact (case-insensitive, whitespace-normalized) match wins outright,
    mirroring materials' find_materials ("an exact match always wins outright
    and is returned alone"). Short of that, every candidate scoring at or
    above _ASK_THRESHOLD is offered, best first, capped at _MAX_CANDIDATES;
    below that threshold, nothing is close enough to mention at all.
    """
    hint = _normalize(name_hint)
    if not hint:
        return Missing(name_hint=name_hint)

    for candidate in candidates:
        if _normalize(candidate.display_name) == hint:
            return Resolved(entity_id=candidate.entity_id, display_name=candidate.display_name)

    scored = sorted(
        (
            (_similarity(hint, _normalize(c.display_name)), c)
            for c in candidates
        ),
        key=lambda pair: pair[0],
        reverse=True,
    )

    above_threshold = [(score, c) for score, c in scored if score >= _ASK_THRESHOLD]
    if not above_threshold:
        return Missing(name_hint=name_hint)

    return Ambiguous(
        candidates=tuple(
            Candidate(entity_id=c.entity_id, display_name=c.display_name)
            for _, c in above_threshold[:_MAX_CANDIDATES]
        )
    )


class MemberNameResolutionService:
    """Wires resolve_name_hint to the org's real active-user roster."""

    def __init__(self, db: PostgresDatabase) -> None:
        self._db = db

    async def resolve(self, *, organization_id: str, name_hint: str) -> ResolutionOutcome:
        candidates = await self._list_active(organization_id)
        return resolve_name_hint(name_hint, candidates)

    async def get_active_display_name(self, *, organization_id: str, entity_id: str) -> str | None:
        """The current full_name for ``entity_id``, or None if it no longer
        names an active user in this org -- a candidate offered in a picker
        may have been deactivated in the gap between the offer and the tap;
        this re-check is what lets the caller treat that honestly as an
        expired selection rather than trusting a stale id."""
        candidates = await self._list_active(organization_id)
        match = next((c for c in candidates if c.entity_id == entity_id), None)
        return match.display_name if match else None

    async def _list_active(self, organization_id: str) -> list[NamedCandidate]:
        import uuid

        from mesiri.infrastructure.postgres.repositories.users import PostgresUserRepository

        async with self._db.transaction() as conn:
            repo = PostgresUserRepository(conn)
            active = await repo.list_active(uuid.UUID(organization_id))
        return [NamedCandidate(entity_id=str(u.id), display_name=u.full_name) for u in active]
