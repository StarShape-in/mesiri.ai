"""Activity target matching — deciding which open Activity a site update is about.

Pure domain: no I/O, no SQL, no AI. Candidates are supplied by the caller (a
repository read, seeded by runtime/inbound_journey.py's `_seed_open_activity`
before the graph runs -- see workflows/runtime.py's docstring); this module
only scores them and says what to do. Mirrors
backend/src/mesiri/domains/workforce/matching.py's shape and reasoning.

This exists to fix a real bug (docs/execution/ACTIVITY_RESOLUTION_AND_
CORRECTION_PLAN.md): before this module, "which activity does this message
continue?" was decided by ordering open activities by `updated_at` and
taking the most recent one, with no check against what the message actually
described. "Finished plastering" could silently mark blockwork COMPLETE if
blockwork was the last thing touched. This module adds the missing check:
compare the message's own `work_type` (if any survived extraction) against
each open candidate's, and only auto-match when there is no ambiguity.

Two decisions are folded into one score, not two:

1. Is this candidate the right activity (work_type comparison)?
2. Does the wording even suggest continuing something, versus starting new
   (`update_kind`)?

`update_kind` never rules a candidate in or out on its own -- it only
shifts confidence, and only ever matters as a tie-breaker for the single-
candidate, no-work-type-stated case (see `resolve_target`'s docstring). The
work_type comparison is the primary signal, because it is the one piece of
evidence that can actually tell two different jobs apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

_CONTINUATION_KINDS = frozenset({"progress", "paused", "resumed", "completed"})


def _normalize(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


class MatchOutcome(str, Enum):
    """What the caller should do with a scored candidate set."""

    #: Exactly one candidate is clearly the right one -- use it silently.
    AUTO_MATCHED = "auto_matched"
    #: Real ambiguity, or a stated work_type that conflicts with the only
    #: open candidate -- ask, offering "this is new work" alongside the
    #: candidates.
    ASK_USER = "ask_user"
    #: No open activities at all -- nothing to compare against, so there is
    #: nothing to ask about either. Create new.
    NO_MATCH = "no_match"


@dataclass(frozen=True, slots=True)
class ActivityCandidate:
    """An open activity being considered as the target for a site update.

    Supplied by the caller (runtime/activity_query.py's
    find_open_activities), never queried by this module.
    """

    activity_id: str
    work_type: str | None
    narrative: str | None


@dataclass(frozen=True, slots=True)
class ScoredActivity:
    activity_id: str
    work_type: str | None
    narrative: str | None
    confidence: float
    #: True when both the message and this candidate stated a work_type and
    #: they disagree -- the caller uses this to word the "which one?"
    #: question as including a clear "this is new work" option, since a
    #: clash is real evidence this candidate is the wrong one, not just an
    #: unclear message.
    clash: bool


@dataclass(frozen=True, slots=True)
class MatchResult:
    outcome: MatchOutcome
    #: Best-first. Empty for NO_MATCH.
    candidates: tuple[ScoredActivity, ...] = ()

    @property
    def matched_activity_id(self) -> str | None:
        """The activity to continue, only when unambiguously auto-matched."""
        if self.outcome is MatchOutcome.AUTO_MATCHED and self.candidates:
            return self.candidates[0].activity_id
        return None


#: A work_type match this strong is used without asking.
AUTO_ACCEPT = 0.75
#: At or above this (but below AUTO_ACCEPT), the candidate is plausible
#: enough to offer as a choice rather than silently discard.
ASK = 0.35

_SCORE_MATCH = 0.9
_SCORE_NEUTRAL = 0.5
_SCORE_CLASH = 0.1


def _score_one(message_work_type: str | None, candidate: ActivityCandidate) -> ScoredActivity:
    message_norm = _normalize(message_work_type)
    candidate_norm = _normalize(candidate.work_type)

    if not message_norm or not candidate_norm:
        return ScoredActivity(
            activity_id=candidate.activity_id,
            work_type=candidate.work_type,
            narrative=candidate.narrative,
            confidence=_SCORE_NEUTRAL,
            clash=False,
        )
    if message_norm == candidate_norm:
        return ScoredActivity(
            activity_id=candidate.activity_id,
            work_type=candidate.work_type,
            narrative=candidate.narrative,
            confidence=_SCORE_MATCH,
            clash=False,
        )
    return ScoredActivity(
        activity_id=candidate.activity_id,
        work_type=candidate.work_type,
        narrative=candidate.narrative,
        confidence=_SCORE_CLASH,
        clash=True,
    )


def resolve_target(
    *,
    message_work_type: str | None,
    update_kind: str | None,
    candidates: list[ActivityCandidate],
) -> MatchResult:
    """Decide which open activity (if any) a site update message is about.

    No candidates -> NO_MATCH: there is nothing to continue, so create a new
    activity (this is the fix for the old "dead end" behaviour -- see
    workflows/site_update/nodes.py).

    A single open candidate, the message states no work_type of its own, and
    `update_kind` is explicitly a continuation word (progress/paused/
    resumed/completed) -> AUTO_MATCHED without asking. This is the single
    most common real case (a running commentary on the one job open on
    site) and the one exception to "ask readily": with only one thing it
    could possibly be, and wording that says it's a continuation, asking
    would be pure friction for no safety gained. Anything less certain than
    this exact combination falls through to asking.

    Otherwise: score every candidate by work_type match. Exactly one
    candidate scoring at or above AUTO_ACCEPT, with no other candidate
    plausible (>= ASK) -> AUTO_MATCHED. Any real ambiguity (more than one
    plausible candidate) or any clash (the message's work_type conflicts
    with a candidate) -> ASK_USER, so a wrong silent append never happens --
    the caller must always include a "this is new work" option alongside
    the candidates it asks about.
    """
    if not candidates:
        return MatchResult(MatchOutcome.NO_MATCH, ())

    scored = tuple(sorted(
        (_score_one(message_work_type, c) for c in candidates),
        key=lambda s: s.confidence,
        reverse=True,
    ))
    best = scored[0]

    if (
        not message_work_type
        and len(candidates) == 1
        and not best.clash
        and _normalize(update_kind) in _CONTINUATION_KINDS
    ):
        return MatchResult(MatchOutcome.AUTO_MATCHED, scored)

    plausible = [s for s in scored if s.confidence >= ASK]
    if best.confidence >= AUTO_ACCEPT and not best.clash and len(plausible) == 1:
        return MatchResult(MatchOutcome.AUTO_MATCHED, scored)
    if plausible or best.clash:
        return MatchResult(MatchOutcome.ASK_USER, scored)
    return MatchResult(MatchOutcome.NO_MATCH, scored)
