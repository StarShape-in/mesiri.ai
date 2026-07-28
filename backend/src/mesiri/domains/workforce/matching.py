"""Worker matching — deciding whether a reported name is someone we know.

Pure domain: no I/O, no SQL, no AI. Candidates are supplied by the caller
(a repository read); this module only scores them and says what to do.

There are two separate questions here, answered by two different functions,
and they are deliberately not the same:

**`match_worker` — "is this attendance line an existing worker?"** Exact
full name AND exact trade, or no match. Nothing else counts. See its
docstring for the reasoning and for the two consequences that follow.

**`score_candidate` — "does this look like somebody already registered?"**
The weighted model below (name, trade, contractor, site history). Used only
by the promotion step's duplicate screen, which asks about one worker at a
time *after* attendance is saved, where a question is cheap.

Everything under "Scoring weights" belongs to the second question. It used
to answer the first as well, until an 80-row register upload turned into
dozens of unanswerable "is this Ravi the same Ravi?" questions inside
WhatsApp. Matching scaled to five workers and not to eighty.

Principle P4 -- a worker is never identified by *part* of a name -- still
holds, more strictly than before: partial names now match nothing at all
rather than being offered as a question. Its counter-pressure, P9 (the
person recording this is on a site and busy), is what drove the switch to a
rule with no questions in it whatsoever.

Smarter matching is expected to come back once the module is stable. The
scoring model is kept intact for that, not merely for the duplicate screen.
"""

from __future__ import annotations

from dataclasses import dataclass
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

    **Exact full name AND exact trade, or no match.** Nothing else links a
    reported worker to the register: not a partial name, not a nickname, not
    a transliteration, not the contractor, and not where they have worked
    before. Anything short of both matching flows to the temporary-worker
    path, and the promotion step afterwards offers them for the register.

    Why the scoring model no longer decides this. It was tuned for a
    supervisor typing five names, where one question is cheap and worth
    asking. That trade-off inverts completely on a register upload: an 80-row
    sheet produced dozens of "is this Ravi the same Ravi?" questions, which
    nobody can answer inside WhatsApp -- the report simply stalls. A rule
    that is dull and predictable beats one that is clever and occasionally
    unanswerable, so matching is now deterministic and states its whole
    reasoning in one line.

    Two consequences worth stating plainly, because both are deliberate:

    - A name with no trade beside it matches nobody, even when the register
      holds exactly one person of that name. A sheet with no Trade column
      therefore matches nothing at all and every row becomes a promotion
      candidate. That is the honest outcome of "both must match" -- and it
      fails toward creating a new worker, which the promotion step lets the
      user catch, rather than toward linking the wrong one, which nobody
      sees.
    - A trade change ("Ravi Kumar" recorded as mason, reported as carpenter)
      is not a match. Under the old model it asked; now it silently becomes a
      new worker, and the promotion duplicate screen is what surfaces it.

    ASK_USER is never returned from here any more. The workflow still knows
    how to ask (see labour_update/nodes.py) and that machinery is kept
    deliberately, because smarter matching is expected to want it back --
    but nothing reaches it while this rule is in force.

    `score_candidate` is untouched and still used, by the promotion step's
    duplicate screen (workflows/worker_promotion/nodes.py), which asks a
    question about one worker at a time *after* attendance is saved. Cheap
    there, unaffordable here.
    """
    reported_name = normalize_name(reported.name)
    if not reported_name:
        return MatchResult(MatchOutcome.NO_MATCH)
    reported_trade = normalize_trade(reported.trade)

    exact = [
        c
        for c in candidates
        if normalize_name(c.name) == reported_name
        and normalize_trade(c.trade) == reported_trade
    ]
    # Two register entries with the same name *and* the same trade cannot be
    # told apart by this rule, and there is no question to fall back on, so
    # neither is chosen. Creating a new worker is recoverable from the
    # dashboard; silently attributing a day's wage to the wrong record is
    # not.
    if len(exact) != 1:
        return MatchResult(MatchOutcome.NO_MATCH)

    winner = exact[0]
    return MatchResult(
        MatchOutcome.AUTO_MATCHED,
        (
            ScoredCandidate(
                winner.worker_id,
                winner.name,
                1.0,
                ("same name", f"same trade ({reported_trade})") if reported_trade
                else ("same name",),
            ),
        ),
    )
