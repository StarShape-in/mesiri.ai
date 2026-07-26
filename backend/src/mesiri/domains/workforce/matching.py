"""Worker matching — deciding whether a reported name is someone we know.

Pure domain: no I/O, no SQL, no AI. Candidates are supplied by the caller
(a repository read); this module only scores them and says what to do.

**The rule this module exists to enforce (plan principle P4): a worker is
never identified by name alone.** `Ravi (Mason)` and `Ravi (Painter)` are
different people, and merging them silently corrupts attendance history in a
way nobody notices until wages are wrong. A perfect name match with no
corroborating signal is therefore capped below the auto-accept threshold by
construction, not by convention — see `_NAME_ONLY_CEILING` and the test that
pins it.

The counter-pressure is principle P9: the person recording this is on a site
and busy. Asking about every worker would make a 10-person report unusable.
So the resolution is deliberate: **P4 governs correctness, P9 governs how
often asking triggers.** Corroborating signals (trade, contractor, having
worked here before) are what earn confidence and keep the question rare. If
supervisors are being asked on most reports, the fix is better signals — not
a lower threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .workers import normalize_name, normalize_trade

# --- Scoring weights -------------------------------------------------------
# Chosen so that no single signal, and no pair that excludes trade, can reach
# AUTO_ACCEPT on its own. See the module docstring.
_W_NAME_EXACT = 0.55
_W_NAME_PARTIAL = 0.30
_W_TRADE = 0.30
_W_CONTRACTOR = 0.20
_W_SEEN_ON_SITE = 0.15
_W_SEEN_ON_PROJECT = 0.10

#: A name match with nothing corroborating it can never exceed this, however
#: perfect the spelling. Kept strictly below AUTO_ACCEPT so "same name" alone
#: always asks.
_NAME_ONLY_CEILING = 0.55

#: At or above this, accept the match without asking.
AUTO_ACCEPT = 0.75

#: At or above this (but below AUTO_ACCEPT), offer as a candidate to choose.
ASK = 0.35


class MatchOutcome(str, Enum):
    """What the caller should do with a scored candidate set."""

    #: Exactly one candidate scored at or above AUTO_ACCEPT — use it silently.
    AUTO_MATCHED = "auto_matched"
    #: Plausible candidates exist — ask the user to pick, or say "someone new".
    ASK_USER = "ask_user"
    #: Nothing plausible — treat as a new (temporary) worker.
    NO_MATCH = "no_match"


@dataclass(frozen=True, slots=True)
class WorkerCandidate:
    """A registered worker being considered as the match for a reported name.

    Supplied by the caller from the workforce register. `seen_on_site` /
    `seen_on_project` mean "this worker has previously been recorded on
    attendance for this site / project" — the strongest cheap corroboration
    available, and the reason matching improves the more the module is used.
    """

    worker_id: str
    name: str
    trade: str | None = None
    contractor: str | None = None
    seen_on_site: bool = False
    seen_on_project: bool = False


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    worker_id: str
    name: str
    confidence: float
    #: Human-readable signals that contributed, for showing in the prompt and
    #: for debugging why a match did or didn't happen.
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MatchResult:
    outcome: MatchOutcome
    #: Best-first. Empty for NO_MATCH.
    candidates: tuple[ScoredCandidate, ...] = ()

    @property
    def matched_worker_id(self) -> str | None:
        """The worker to use, only when unambiguously auto-matched."""
        if self.outcome is MatchOutcome.AUTO_MATCHED and self.candidates:
            return self.candidates[0].worker_id
        return None


@dataclass(frozen=True, slots=True)
class ReportedWorker:
    """What the AI extracted (or the user typed) about one person."""

    name: str
    trade: str | None = None
    contractor: str | None = None
    daily_wage: object | None = None
    notes: str | None = None
    #: Free-text activity/work item this person worked on, if stated.
    #: Carried through even though V1 exposes no activity management, so the
    #: Materials -> Activity -> Labour -> Expenses link can be made later
    #: (plan principle P7). It cannot be reconstructed after the fact.
    activity: str | None = None


def _name_score(reported: str, candidate: str) -> tuple[float, str | None]:
    """Score name similarity. Conservative: no fuzzy edit-distance matching.

    Deliberately not using fuzzy string distance. On a site roster, one
    character often *is* the difference between two people (Sunil/Sunita,
    Ramesh/Rakesh), and a near-miss that scores highly is exactly how a
    false merge happens. Exact and containment matches only; anything less
    certain is left for the user to resolve.
    """
    a, b = normalize_name(reported), normalize_name(candidate)
    if not a or not b:
        return 0.0, None
    if a == b:
        return _W_NAME_EXACT, "same name"
    a_parts, b_parts = a.split(), b.split()
    # "Ravi" reported against "Ravi Kumar" registered, or vice versa: a real
    # partial signal, but weaker -- first names collide constantly on site.
    if set(a_parts) & set(b_parts):
        return _W_NAME_PARTIAL, "part of the name matches"
    return 0.0, None


def score_candidate(reported: ReportedWorker, candidate: WorkerCandidate) -> ScoredCandidate:
    """Score one candidate against the reported worker.

    Returns 0.0 when the names share nothing — trade or contractor agreement
    alone must never suggest a specific person, only that the *kind* of
    worker is plausible.
    """
    name_score, name_reason = _name_score(reported.name, candidate.name)
    if name_score == 0.0:
        return ScoredCandidate(candidate.worker_id, candidate.name, 0.0, ())

    score = name_score
    reasons: list[str] = [name_reason] if name_reason else []

    reported_trade = normalize_trade(reported.trade)
    candidate_trade = normalize_trade(candidate.trade)
    if reported_trade and candidate_trade:
        if reported_trade == candidate_trade:
            score += _W_TRADE
            reasons.append(f"same trade ({candidate_trade.replace('_', ' ')})")
        else:
            # A stated, *different* trade is strong evidence of a different
            # person -- this is the Ravi-the-Mason vs Ravi-the-Painter case.
            # Zero it out rather than merely not adding: a same-name,
            # different-trade pair must never be offered as a likely match.
            return ScoredCandidate(
                candidate.worker_id,
                candidate.name,
                0.0,
                ("different trade — treated as a different person",),
            )

    if reported.contractor and candidate.contractor:
        if normalize_name(reported.contractor) == normalize_name(candidate.contractor):
            score += _W_CONTRACTOR
            reasons.append("same contractor")

    if candidate.seen_on_site:
        score += _W_SEEN_ON_SITE
        reasons.append("worked on this site before")
    elif candidate.seen_on_project:
        score += _W_SEEN_ON_PROJECT
        reasons.append("worked on this project before")

    # The P4 guarantee, enforced structurally: with no corroboration beyond
    # the name itself, confidence cannot reach AUTO_ACCEPT no matter how
    # exact the spelling.
    if len(reasons) <= 1:
        score = min(score, _NAME_ONLY_CEILING)

    return ScoredCandidate(candidate.worker_id, candidate.name, round(min(score, 1.0), 4), tuple(reasons))


def match_worker(
    reported: ReportedWorker, candidates: list[WorkerCandidate]
) -> MatchResult:
    """Decide whether `reported` is one of `candidates`.

    Auto-accepts only when a single candidate clears AUTO_ACCEPT. Two
    candidates both clearing it is *more* ambiguous, not less — that asks.
    """
    scored = sorted(
        (score_candidate(reported, c) for c in candidates),
        key=lambda s: s.confidence,
        reverse=True,
    )
    plausible = tuple(s for s in scored if s.confidence >= ASK)

    if not plausible:
        return MatchResult(MatchOutcome.NO_MATCH)

    confident = [s for s in plausible if s.confidence >= AUTO_ACCEPT]
    if len(confident) == 1:
        return MatchResult(MatchOutcome.AUTO_MATCHED, (confident[0],))

    return MatchResult(MatchOutcome.ASK_USER, plausible)
