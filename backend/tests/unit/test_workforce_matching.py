"""Worker matching — the rules that stop attendance history being corrupted.

The load-bearing rule (Labour plan principle P4): **a worker is never
identified by name alone.** A silent false merge is the worst failure this
module can produce — nobody notices until wages are wrong, and attendance is
immutable so it cannot simply be corrected.

These tests pin the invariants rather than the exact numbers, so the weights
can be retuned without rewriting the suite; where a specific threshold matters
it is asserted through behaviour (which outcome results), not the constant.
"""

from __future__ import annotations

import pytest

from mesiri.domains.workforce.matching import (
    ASK,
    AUTO_ACCEPT,
    MatchOutcome,
    ReportedWorker,
    WorkerCandidate,
    match_worker,
    score_candidate,
)


def _candidates(*cs: WorkerCandidate) -> list[WorkerCandidate]:
    return list(cs)


# ---------------------------------------------------------------------------
# P4 — never by name alone
# ---------------------------------------------------------------------------


def test_perfect_name_match_alone_never_auto_matches():
    """The single most important assertion in this module.

    A flawless name match with nothing corroborating it must still ask. If
    this ever passes silently, two different people with the same name get
    merged and their attendance is wrong from then on.
    """
    reported = ReportedWorker(name="Ravi")
    result = match_worker(reported, _candidates(WorkerCandidate("w1", "Ravi")))

    assert result.outcome is MatchOutcome.ASK_USER
    assert result.matched_worker_id is None


def test_name_only_confidence_stays_below_the_auto_accept_threshold():
    """Enforced structurally by the ceiling, not by weights happening to sum
    low — so adding a future signal can't accidentally break P4."""
    scored = score_candidate(
        ReportedWorker(name="Ravi Kumar"), WorkerCandidate("w1", "Ravi Kumar")
    )
    assert scored.confidence < AUTO_ACCEPT


def test_same_name_different_trade_asks_rather_than_deciding():
    """`Ravi (Mason)` vs `Ravi (Painter)` — the canonical ambiguous case.

    Both readings are plausible: a different Ravi, or the same Ravi who has
    changed trade. Guessing either way is harmful — assume "different" and
    one worker's history splits in two; assume "same" and two people merge.
    So it always asks.
    """
    reported = ReportedWorker(name="Ravi", trade="Painter")
    result = match_worker(reported, _candidates(WorkerCandidate("w1", "Ravi", trade="mason")))

    assert result.outcome is MatchOutcome.ASK_USER
    assert result.matched_worker_id is None
    assert result.candidates[0].trade_changed is True


def test_a_worker_who_changed_trade_is_still_offered_as_a_candidate():
    """Trades genuinely change on site: a helper is promoted to mason,
    someone lays brick one day and does carpentry the next. Treating a
    mismatch as disqualifying would quietly create a second register entry
    for the same person and split their history."""
    result = match_worker(
        ReportedWorker(name="Ravi", trade="Mason"),
        _candidates(WorkerCandidate("w1", "Ravi", trade="helper", seen_on_site=True)),
    )
    assert result.outcome is MatchOutcome.ASK_USER
    assert [c.worker_id for c in result.candidates] == ["w1"]


def test_a_trade_change_never_auto_matches_however_strong_the_rest():
    """Even with the same contractor and prior history on this very site, a
    changed trade is confirmed rather than assumed — the ceiling holds."""
    result = match_worker(
        ReportedWorker(name="Ravi", trade="Mason", contractor="ABC Labour"),
        _candidates(
            WorkerCandidate(
                "w1", "Ravi", trade="helper", contractor="ABC Labour", seen_on_site=True
            )
        ),
    )
    assert result.outcome is MatchOutcome.ASK_USER
    assert result.candidates[0].trade_changed is True


def test_trade_change_reason_names_both_trades():
    """The prompt has to be able to say "register says mason, report says
    carpenter" — a bare "which of these?" doesn't tell the user what decision
    they are actually making."""
    scored = score_candidate(
        ReportedWorker(name="Ravi", trade="Carpenter"),
        WorkerCandidate("w1", "Ravi", trade="mason"),
    )
    joined = " ".join(scored.reasons).lower()
    assert "mason" in joined and "carpenter" in joined


def test_trade_mismatch_alone_does_not_lift_a_name_only_match():
    """A disagreeing trade is not corroboration — it must not be what pushes
    a bare name match over the ask threshold."""
    scored = score_candidate(
        ReportedWorker(name="Ravi", trade="Painter"),
        WorkerCandidate("w1", "Ravi", trade="mason"),
    )
    assert scored.confidence < AUTO_ACCEPT


def test_trade_alone_never_identifies_a_person():
    """Two masons are not the same mason. Trade agreement without any name
    overlap must score nothing."""
    scored = score_candidate(
        ReportedWorker(name="Suresh", trade="mason"),
        WorkerCandidate("w1", "Ramesh", trade="mason", seen_on_site=True),
    )
    assert scored.confidence == 0.0


def test_contractor_alone_never_identifies_a_person():
    scored = score_candidate(
        ReportedWorker(name="Suresh", contractor="ABC Labour"),
        WorkerCandidate("w1", "Ramesh", contractor="ABC Labour"),
    )
    assert scored.confidence == 0.0


# ---------------------------------------------------------------------------
# Corroboration earns confidence (P9 — keep the asking rare)
# ---------------------------------------------------------------------------


def test_name_plus_trade_plus_history_auto_matches():
    """The common good case: a known worker, same trade, worked here before.
    This must NOT ask — asking on every routine worker would make a 10-person
    report unusable (P9)."""
    reported = ReportedWorker(name="Ravi", trade="Mason")
    result = match_worker(
        reported,
        _candidates(WorkerCandidate("w1", "Ravi", trade="mason", seen_on_site=True)),
    )

    assert result.outcome is MatchOutcome.AUTO_MATCHED
    assert result.matched_worker_id == "w1"


def test_trade_synonyms_still_corroborate():
    """"Mistri" and "mason" are the same trade on an Indian site; treating
    them as different would push a routine match into asking."""
    reported = ReportedWorker(name="Ravi", trade="Mistri")
    result = match_worker(
        reported,
        _candidates(WorkerCandidate("w1", "Ravi", trade="Mason", seen_on_site=True)),
    )
    assert result.outcome is MatchOutcome.AUTO_MATCHED


def test_history_on_project_counts_less_than_history_on_this_site():
    on_site = score_candidate(
        ReportedWorker(name="Ravi", trade="mason"),
        WorkerCandidate("w1", "Ravi", trade="mason", seen_on_site=True),
    )
    on_project = score_candidate(
        ReportedWorker(name="Ravi", trade="mason"),
        WorkerCandidate("w2", "Ravi", trade="mason", seen_on_project=True),
    )
    assert on_site.confidence > on_project.confidence


def test_scored_candidates_explain_themselves():
    """The prompt shows these reasons to the user, and they are what makes a
    wrong match noticeable before it is confirmed."""
    scored = score_candidate(
        ReportedWorker(name="Ravi", trade="mason", contractor="ABC"),
        WorkerCandidate("w1", "Ravi", trade="mason", contractor="ABC", seen_on_site=True),
    )
    joined = " ".join(scored.reasons).lower()
    assert "name" in joined
    assert "trade" in joined
    assert "contractor" in joined
    assert "site" in joined


# ---------------------------------------------------------------------------
# Ambiguity must ask, never pick
# ---------------------------------------------------------------------------


def test_two_equally_strong_candidates_ask_rather_than_guess():
    """Two confident matches are *more* ambiguous than one, not less."""
    reported = ReportedWorker(name="Ravi", trade="mason")
    result = match_worker(
        reported,
        _candidates(
            WorkerCandidate("w1", "Ravi", trade="mason", seen_on_site=True),
            WorkerCandidate("w2", "Ravi", trade="mason", seen_on_site=True),
        ),
    )

    assert result.outcome is MatchOutcome.ASK_USER
    assert result.matched_worker_id is None
    assert len(result.candidates) == 2


def test_candidates_are_offered_best_first():
    reported = ReportedWorker(name="Ravi", trade="mason")
    result = match_worker(
        reported,
        _candidates(
            WorkerCandidate("weak", "Ravi"),
            WorkerCandidate("strong", "Ravi", trade="mason", seen_on_site=True),
        ),
    )
    assert [c.worker_id for c in result.candidates][0] == "strong"


def test_no_candidates_is_no_match_not_an_error():
    """An empty register is the normal state on day one — every worker is new
    then, and that must flow into the temporary-worker path rather than
    failing."""
    result = match_worker(ReportedWorker(name="Ravi"), [])
    assert result.outcome is MatchOutcome.NO_MATCH
    assert result.candidates == ()


def test_unrelated_names_are_not_offered_at_all():
    result = match_worker(
        ReportedWorker(name="Ravi"), _candidates(WorkerCandidate("w1", "Mahesh"))
    )
    assert result.outcome is MatchOutcome.NO_MATCH


# ---------------------------------------------------------------------------
# Partial names — real, but weak
# ---------------------------------------------------------------------------


def test_partial_name_match_is_weaker_than_exact():
    exact = score_candidate(ReportedWorker(name="Ravi Kumar"), WorkerCandidate("w1", "Ravi Kumar"))
    partial = score_candidate(ReportedWorker(name="Ravi"), WorkerCandidate("w1", "Ravi Kumar"))
    assert partial.confidence < exact.confidence


def test_partial_name_alone_reaches_the_ask_threshold_but_not_auto_accept():
    """A bare first name against a full name is weak evidence — too weak to
    act on silently, but strong enough that it must surface as a question.

    Landing below ASK let a registered worker's own name, typed the short
    way, resolve to NO_MATCH with no question ever shown — the report
    silently created a second, unlinked identity instead of asking "is this
    the Ravi Kumar already on the register?"
    """
    scored = score_candidate(ReportedWorker(name="Ravi"), WorkerCandidate("w1", "Ravi Kumar"))
    assert ASK <= scored.confidence < AUTO_ACCEPT


def test_partial_name_alone_asks_rather_than_silently_becoming_a_new_worker():
    result = match_worker(ReportedWorker(name="Ravi"), _candidates(WorkerCandidate("w1", "Ravi Kumar")))
    assert result.outcome is MatchOutcome.ASK_USER
    assert result.matched_worker_id is None


@pytest.mark.parametrize(
    ("reported_name", "candidate_name"),
    [("Sunil", "Sunita"), ("Ramesh", "Rakesh"), ("Anil", "Anita")],
)
def test_near_miss_names_are_not_treated_as_the_same_person(reported_name, candidate_name):
    """No fuzzy edit-distance matching, deliberately. On a roster one
    character often *is* the difference between two people, and a near-miss
    scoring highly is precisely how a false merge happens."""
    scored = score_candidate(
        ReportedWorker(name=reported_name), WorkerCandidate("w1", candidate_name)
    )
    assert scored.confidence == 0.0


# ---------------------------------------------------------------------------
# Input robustness — extraction output is messy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["  Ravi  ", "RAVI", "ravi", "Ravi.", "Ravi-Kumar"])
def test_name_comparison_is_insensitive_to_case_spacing_and_punctuation(name):
    scored = score_candidate(
        ReportedWorker(name=name, trade="mason"),
        WorkerCandidate("w1", "Ravi Kumar", trade="mason", seen_on_site=True),
    )
    assert scored.confidence >= ASK


def test_empty_reported_name_matches_nothing():
    scored = score_candidate(ReportedWorker(name=""), WorkerCandidate("w1", "Ravi"))
    assert scored.confidence == 0.0


def test_missing_trade_on_either_side_does_not_penalise():
    """A report that omits trade is normal and fast (P9) — it should simply
    not corroborate, rather than counting against the match."""
    no_trade = score_candidate(
        ReportedWorker(name="Ravi"), WorkerCandidate("w1", "Ravi", trade="mason")
    )
    assert no_trade.confidence > 0.0


# ---------------------------------------------------------------------------
# Everything below ASK becomes a temporary worker — duplicates are caught
# later, at promotion time, not here
# ---------------------------------------------------------------------------


def test_partial_name_with_a_trade_mismatch_falls_below_ask():
    """"Ravi, carpenter" against registered "Ravi Kumar, mason": the partial
    name (0.35) minus the trade penalty (0.15) lands under ASK, so attendance
    records a temporary worker without asking anything.

    That is deliberate -- the attendance flow stays fast (P9) and never stops
    to interrogate a weak signal. The duplicate is caught afterwards, by the
    promotion step's own name/trade/contractor check, where asking costs
    nothing because attendance is already saved."""
    scored = score_candidate(
        ReportedWorker(name="Ravi", trade="carpenter"),
        WorkerCandidate("w1", "Ravi Kumar", trade="mason"),
    )
    assert scored.confidence < ASK

    result = match_worker(
        ReportedWorker(name="Ravi", trade="carpenter"),
        _candidates(WorkerCandidate("w1", "Ravi Kumar", trade="mason")),
    )
    assert result.outcome is MatchOutcome.NO_MATCH


def test_trade_contractor_and_site_history_alone_never_identify_a_person():
    """A completely different name, however strongly everything else
    corroborates, is never a match. Trade, contractor and site/project
    history only ever corroborate a name that already matched something --
    they must never suggest a specific person by themselves (P4)."""
    strong_but_wrong_name = WorkerCandidate(
        "w1", "Ravi", trade="mason", contractor="ABC Labour", seen_on_site=True
    )
    scored = score_candidate(
        ReportedWorker(name="Suresh", trade="mason"), strong_but_wrong_name
    )
    assert scored.confidence == 0.0

    result = match_worker(
        ReportedWorker(name="Suresh", trade="mason"), _candidates(strong_but_wrong_name)
    )
    assert result.outcome is MatchOutcome.NO_MATCH


def test_transliteration_miss_with_site_history_is_still_no_match():
    """A worker seen on this site before, reported with a spelling sharing no
    token with their registered name, scores nothing -- catching it would
    need fuzzy name matching, which this module deliberately avoids (see
    _name_score's docstring)."""
    scored = score_candidate(
        ReportedWorker(name="Raavi"),
        WorkerCandidate("w1", "Ravi", seen_on_site=True),
    )
    assert scored.confidence == 0.0


# ---------------------------------------------------------------------------
# Unique full-name match — recognising a registered worker without a question
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("reported_trade", "registered_trade", "case"),
    [
        ("carpenter", "carpenter", "both state the same trade"),
        ("carpenter", None, "added from the dashboard without a trade"),
        (None, "carpenter", "the sheet lists names only"),
        (None, None, "neither side states a trade"),
        ("Carpentry", "Carpenter", "the same trade worded differently"),
    ],
)
def test_a_uniquely_named_registered_worker_is_recognised(
    reported_trade, registered_trade, case
):
    """The bug this fixes, reported from real use: "Ilan Usman" is already a
    permanent worker, yet attendance kept treating him as somebody new --
    so he was offered for promotion again every single day.

    An exact full-name match scores 0.55, which only reaches AUTO_ACCEPT when
    a trade is stated on *both* sides and agrees. Every other case asked
    "which Ilan Usman?" about the only Ilan Usman on the register.
    """
    result = match_worker(
        ReportedWorker(name="Ilan Usman", trade=reported_trade),
        _candidates(WorkerCandidate("w1", "Ilan Usman", trade=registered_trade)),
    )
    assert result.outcome is MatchOutcome.AUTO_MATCHED, case
    assert result.matched_worker_id == "w1", case


def test_two_workers_sharing_a_full_name_still_ask():
    """The uniqueness guard is what keeps the rule above honest under P4 --
    the moment the name stops identifying one person, it stops deciding."""
    result = match_worker(
        ReportedWorker(name="Ilan Usman"),
        _candidates(
            WorkerCandidate("w1", "Ilan Usman", trade="carpenter"),
            WorkerCandidate("w2", "Ilan Usman", trade="painter"),
        ),
    )
    assert result.outcome is MatchOutcome.ASK_USER
    assert result.matched_worker_id is None


def test_a_full_name_match_with_a_changed_trade_is_still_confirmed():
    """A full name makes "different person" less likely, not impossible, and
    the two readings need different answers -- so the trade-change rule holds
    here exactly as it does for a first name."""
    result = match_worker(
        ReportedWorker(name="Ilan Usman", trade="mason"),
        _candidates(WorkerCandidate("w1", "Ilan Usman", trade="carpenter")),
    )
    assert result.outcome is MatchOutcome.ASK_USER
    assert result.candidates[0].trade_changed is True


def test_a_bare_first_name_is_never_auto_matched_by_the_full_name_rule():
    """P4's canonical case, unchanged: first names collide constantly on a
    site, so one part of a name never decides on its own."""
    assert (
        match_worker(
            ReportedWorker(name="Ravi"), _candidates(WorkerCandidate("w1", "Ravi"))
        ).outcome
        is MatchOutcome.ASK_USER
    )
    # ...including when the register holds the full version of that name.
    assert (
        match_worker(
            ReportedWorker(name="Ilan"), _candidates(WorkerCandidate("w1", "Ilan Usman"))
        ).outcome
        is MatchOutcome.ASK_USER
    )


def test_the_full_name_rule_ignores_case_and_spacing():
    result = match_worker(
        ReportedWorker(name="  ilan   USMAN "),
        _candidates(WorkerCandidate("w1", "Ilan Usman")),
    )
    assert result.matched_worker_id == "w1"


def test_a_genuinely_new_full_name_is_still_no_match():
    """Recognising known workers must not start inventing matches for
    unknown ones -- a new name still flows to the temporary-worker path."""
    result = match_worker(
        ReportedWorker(name="Rahul Nair"),
        _candidates(WorkerCandidate("w1", "Ilan Usman", trade="carpenter")),
    )
    assert result.outcome is MatchOutcome.NO_MATCH
