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
from dataclasses import replace as dataclasses_replace
from enum import Enum

from .workers import normalize_name, normalize_trade

# --- Scoring weights -------------------------------------------------------
# Chosen so that no single signal, and no pair that excludes trade, can reach
# AUTO_ACCEPT on its own. See the module docstring.
_W_NAME_EXACT = 0.55
#: Equal to ASK, not below it: a same-first-name match with nothing else
#: corroborating it ("Ravi" reported against registered "Ravi Kumar") must
#: still surface as a question. Landing under ASK made this silently resolve
#: to NO_MATCH -- a registered worker's own name, typed the short way,
#: created a second identity instead of asking which Ravi was meant.
_W_NAME_PARTIAL = 0.35
_W_TRADE = 0.30
_W_CONTRACTOR = 0.20
_W_SEEN_ON_SITE = 0.15
_W_SEEN_ON_PROJECT = 0.10

#: Penalty when both sides state a trade and they disagree. A reduction, not
#: an elimination -- see _TRADE_MISMATCH_CEILING.
_W_TRADE_MISMATCH = 0.15

#: A name match with nothing corroborating it can never exceed this, however
#: perfect the spelling. Kept strictly below AUTO_ACCEPT so "same name" alone
#: always asks.
_NAME_ONLY_CEILING = 0.55

#: A trade mismatch can never auto-accept, however much else corroborates it.
#: People genuinely change trade -- a helper becomes a mason, someone works
#: mason one day and carpenter the next -- so a mismatch must not be treated
#: as proof of a different person. But it must always be confirmed, because
#: the alternative reading (a different Ravi) is equally plausible and
#: guessing wrong either fragments one worker's history or merges two.
_TRADE_MISMATCH_CEILING = 0.70

#: At or above this, accept the match without asking.
AUTO_ACCEPT = 0.75

#: At or above this (but below AUTO_ACCEPT), offer as a candidate to choose.
ASK = 0.35

#: At or above this (but below ASK), surface as a low-confidence candidate
#: rather than silently creating a new temporary worker.
#:
#: Reachable only via partial name overlap plus a trade mismatch (0.35 - 0.15
#: = 0.20 exactly): "Ravi, carpenter" reported against registered "Ravi
#: Kumar, mason". Before this band existed, that case fell silently to
#: NO_MATCH -- a real partial-name signal was thrown away because the trade
#: penalty alone dragged it under ASK. It is *not* reachable from trade,
#: contractor or site/project history alone with zero name overlap: those
#: signals only ever corroborate a name that already matched something
#: (score_candidate returns 0.0 outright when the names share nothing --
#: see its docstring). A pure transliteration miss ("Ravi" vs "Raavi") scores
#: 0.0 and is correctly NO_MATCH, not a soft match; catching that would need
#: fuzzy name matching, which this module deliberately avoids (see
#: _name_score's docstring).
#: Below this threshold (< 0.20), there is genuinely no signal and
#: NO_MATCH is the correct and honest answer -- no guessing.
SOFT_MATCH = 0.20


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
    #: True when both sides stated a trade and they disagree. The caller uses
    #: this to word the question as "same worker, updated trade?" rather than
    #: a bare "which of these?" -- the two readings need different answers.
    trade_changed: bool = False
    #: True when confidence is in [SOFT_MATCH, ASK) -- see SOFT_MATCH's
    #: docstring for exactly which case reaches this band. The prompt labels
    #: these "(possible match)" to set the right expectation, and the user
    #: may still pick "Someone new" to dismiss them.
    low_confidence: bool = False


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
    trade_changed = False
    if reported_trade and candidate_trade:
        if reported_trade == candidate_trade:
            score += _W_TRADE
            reasons.append(f"same trade ({candidate_trade.replace('_', ' ')})")
        else:
            # A different trade lowers confidence but does NOT prove a
            # different person. Trades genuinely change on site: a helper is
            # promoted to mason, someone lays brick one day and does
            # carpentry the next. Treating a mismatch as disqualifying would
            # quietly create a second register entry for the same person and
            # split their history in two.
            #
            # It is equally wrong to assume it *is* the same person, so this
            # always lands in the ask band (see _TRADE_MISMATCH_CEILING) and
            # the user resolves it: same worker with an updated trade, or a
            # different worker who shares a name?
            trade_changed = True
            score -= _W_TRADE_MISMATCH
            reasons.append(
                f"different trade (register says {candidate_trade.replace('_', ' ')}, "
                f"report says {reported_trade.replace('_', ' ')})"
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
    # exact the spelling. A trade mismatch is not corroboration, so it does
    # not lift the name out of this ceiling on its own.
    corroborating = [r for r in reasons if not r.startswith("different trade")]
    if len(corroborating) <= 1:
        score = min(score, _NAME_ONLY_CEILING)

    # A changed trade always gets confirmed, however strong the rest.
    if trade_changed:
        score = min(score, _TRADE_MISMATCH_CEILING)

    return ScoredCandidate(
        candidate.worker_id,
        candidate.name,
        round(max(min(score, 1.0), 0.0), 4),
        tuple(reasons),
        trade_changed=trade_changed,
    )


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

    if plausible:
        confident = [s for s in plausible if s.confidence >= AUTO_ACCEPT]
        if len(confident) == 1:
            return MatchResult(MatchOutcome.AUTO_MATCHED, (confident[0],))
        return MatchResult(MatchOutcome.ASK_USER, plausible)

    # Soft-match band: no candidate cleared ASK, but at least one has a faint
    # signal (e.g. seen_on_site without any name overlap). Ask the user rather
    # than silently creating a duplicate temp (principle P4 extended).
    soft = tuple(
        dataclasses_replace(s, low_confidence=True)
        for s in scored
        if s.confidence >= SOFT_MATCH
    )
    if soft:
        return MatchResult(MatchOutcome.ASK_USER, soft)

    return MatchResult(MatchOutcome.NO_MATCH)
