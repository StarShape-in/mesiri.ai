"""Worker matching — two separate questions, two separate contracts.

**`match_worker` — "is this attendance line an existing worker?"** Exact full
name AND exact trade, or no match. No fuzzy matching, no partial names, no
contractor, no site history, no confidence, and — importantly — no
questions. Every test in the first half asserts that rule and nothing else.

**`score_candidate` — "does this look like somebody already registered?"**
The weighted model, now used only by the promotion step's duplicate screen,
which asks about one worker at a time *after* attendance is saved. The
second half covers that, unchanged.

Why they split. The weighted model answered both questions until an 80-row
register upload turned into dozens of "is this Ravi the same Ravi?"
questions inside WhatsApp. It scaled to five workers and not to eighty, so
attendance matching became deterministic and the model stayed where a
question is still affordable.

P4 -- a worker is never identified by *part* of a name -- is not weakened by
this. It is stricter: a partial name now matches nothing at all, where
before it was offered as a question.
"""

from __future__ import annotations

import pytest

from mesiri.domains.workforce.matching import (
    MatchOutcome,
    ReportedWorker,
    WorkerCandidate,
    match_worker,
    score_candidate,
)


def _candidates(*cs: WorkerCandidate) -> list[WorkerCandidate]:
    return list(cs)


#: The register used across the attendance-matching tests, mirroring the
#: worked example this rule was specified against.
REGISTER = [
    WorkerCandidate("w-ilan", "Ilan Usman", trade="carpenter"),
    WorkerCandidate("w-ravi", "Ravi Kumar", trade="mason"),
    WorkerCandidate("w-ajith", "Ajith N", trade="helper"),
]


# ===========================================================================
# match_worker — exact name AND exact trade, or nothing
# ===========================================================================


@pytest.mark.parametrize(
    ("name", "trade", "expected_id"),
    [
        ("Ilan Usman", "Carpenter", "w-ilan"),
        ("Ravi Kumar", "Mason", "w-ravi"),
        ("Ajith N", "Helper", "w-ajith"),
    ],
)
def test_an_exact_name_and_trade_matches_with_no_question(name, trade, expected_id):
    result = match_worker(ReportedWorker(name=name, trade=trade), REGISTER)

    assert result.outcome is MatchOutcome.AUTO_MATCHED
    assert result.matched_worker_id == expected_id


@pytest.mark.parametrize(
    ("name", "trade", "why"),
    [
        ("Ilan Usman", "Mason", "right name, wrong trade"),
        ("Ravi Kumar", "Carpenter", "right name, wrong trade"),
        ("Ilan", None, "part of a name, no trade"),
        ("Ravi", None, "part of a name, no trade"),
        ("Ajith", "helper", "part of a name, right trade"),
        ("Ilan Usman", None, "right name, no trade stated"),
        ("Suresh Babu", "mason", "nobody of that name"),
        ("", "mason", "no name at all"),
    ],
)
def test_anything_short_of_both_is_not_a_match(name, trade, why):
    """The whole rule, from the other side. Each of these becomes a temporary
    worker and is offered for the register afterwards, which is recoverable
    -- whereas linking the wrong person is not."""
    result = match_worker(ReportedWorker(name=name, trade=trade), REGISTER)

    assert result.outcome is MatchOutcome.NO_MATCH, why
    assert result.matched_worker_id is None, why


def test_a_name_with_no_trade_beside_it_matches_nobody():
    """Called out on its own because it is the consequence people are most
    likely to be surprised by: a sheet with no Trade column matches nothing
    at all, and every row becomes a promotion candidate.

    That is the honest reading of "both must match", and it fails toward
    creating a new worker -- which the promotion step lets the user catch --
    rather than toward linking the wrong one, which nobody sees.
    """
    result = match_worker(ReportedWorker(name="Ilan Usman"), REGISTER)

    assert result.outcome is MatchOutcome.NO_MATCH


def test_a_worker_with_no_trade_on_either_side_still_matches():
    """Both absent is still "the same", so a register kept without trades
    stays usable when the report omits them too."""
    register = [WorkerCandidate("w1", "Ilan Usman")]
    result = match_worker(ReportedWorker(name="Ilan Usman"), register)

    assert result.matched_worker_id == "w1"


@pytest.mark.parametrize(
    "name", ["ILAN USMAN", "ilan usman", "  Ilan   Usman  ", "Ilan-Usman", "Ilan Usman."]
)
def test_matching_ignores_case_spacing_and_punctuation(name):
    """"Exact" means the same name, not the same keystrokes -- OCR returns
    whole sheets in capitals."""
    result = match_worker(ReportedWorker(name=name, trade="carpenter"), REGISTER)

    assert result.matched_worker_id == "w-ilan"


@pytest.mark.parametrize("trade", ["CARPENTER", "Carpenter", "carpenter", "Carpentry"])
def test_matching_ignores_trade_casing_and_wording(trade):
    """Same for the trade: "Carpentry" and "Carpenter" are one trade, and
    treating them as two would break a match that is plainly correct."""
    result = match_worker(ReportedWorker(name="Ilan Usman", trade=trade), REGISTER)

    assert result.matched_worker_id == "w-ilan"


def test_two_identical_register_entries_match_neither():
    """There is no question to fall back on any more, so an ambiguous
    register cannot be resolved. Creating a new worker is fixable from the
    dashboard; attributing a day's wage to the wrong record is not."""
    register = [
        WorkerCandidate("w1", "Ravi Kumar", trade="mason"),
        WorkerCandidate("w2", "Ravi Kumar", trade="mason"),
    ]
    result = match_worker(ReportedWorker(name="Ravi Kumar", trade="mason"), register)

    assert result.outcome is MatchOutcome.NO_MATCH


def test_an_empty_register_is_no_match_not_an_error():
    """Day one: nobody is registered, so every named worker is new."""
    assert match_worker(ReportedWorker(name="Ravi Kumar", trade="mason"), []).outcome is (
        MatchOutcome.NO_MATCH
    )


def test_matching_never_asks_a_question():
    """The property that makes an 80-row upload usable. Reported from
    testing: a register upload produced dozens of "is this Ravi the same
    Ravi?" questions, which nobody can answer inside WhatsApp."""
    reports = [
        ReportedWorker(name="Ravi", trade="mason"),
        ReportedWorker(name="Ravi Kumar", trade="carpenter"),
        ReportedWorker(name="Ilan", trade="carpenter"),
        ReportedWorker(name="Ilan Usman", trade="carpenter"),
        ReportedWorker(name="Ajith N"),
    ]
    outcomes = {match_worker(r, REGISTER).outcome for r in reports}

    assert MatchOutcome.ASK_USER not in outcomes


def test_neither_contractor_nor_site_history_can_produce_a_match():
    """Explicitly dropped for this phase. Both are still carried on the
    candidate and still feed score_candidate, so re-enabling them later is a
    change to one function rather than a re-plumb."""
    register = [
        WorkerCandidate(
            "w1",
            "Ravi Kumar",
            trade="carpenter",
            contractor="ABC Labour",
            seen_on_site=True,
            seen_on_project=True,
        )
    ]
    result = match_worker(
        ReportedWorker(name="Ravi Kumar", trade="mason", contractor="ABC Labour"),
        register,
    )

    assert result.outcome is MatchOutcome.NO_MATCH


@pytest.mark.parametrize(
    ("reported_name", "candidate_name"),
    [("Sunil", "Sunita"), ("Ramesh", "Rakesh"), ("Anil", "Anita"), ("Raavi", "Ravi")],
)
def test_near_miss_names_never_match(reported_name, candidate_name):
    """No fuzzy matching, deliberately. On a roster one character often *is*
    the difference between two people."""
    register = [WorkerCandidate("w1", candidate_name, trade="mason")]
    result = match_worker(ReportedWorker(name=reported_name, trade="mason"), register)

    assert result.outcome is MatchOutcome.NO_MATCH


# ===========================================================================
# score_candidate — the weighted model, now used only by the duplicate screen
# ===========================================================================


def test_a_name_on_its_own_never_reaches_auto_accept():
    """P4 at the scoring level. The duplicate screen leans on this: a bare
    name should raise a question, not silently decide."""
    from mesiri.domains.workforce.matching import AUTO_ACCEPT

    scored = score_candidate(ReportedWorker(name="Ravi"), WorkerCandidate("w1", "Ravi"))
    assert scored.confidence < AUTO_ACCEPT


def test_trade_alone_never_identifies_a_person():
    scored = score_candidate(
        ReportedWorker(name="Ravi", trade="mason"),
        WorkerCandidate("w1", "Ramesh", trade="mason", seen_on_site=True),
    )
    assert scored.confidence == 0.0


def test_contractor_alone_never_identifies_a_person():
    scored = score_candidate(
        ReportedWorker(name="Ravi", contractor="ABC Labour"),
        WorkerCandidate("w1", "Ramesh", contractor="ABC Labour"),
    )
    assert scored.confidence == 0.0


def test_trade_synonyms_corroborate():
    """"Mistri" and "mason" are the same trade on an Indian site."""
    same = score_candidate(
        ReportedWorker(name="Ravi", trade="Mistri"),
        WorkerCandidate("w1", "Ravi", trade="Mason"),
    )
    bare = score_candidate(ReportedWorker(name="Ravi"), WorkerCandidate("w1", "Ravi"))
    assert same.confidence > bare.confidence


def test_history_on_this_site_counts_more_than_on_the_project():
    on_site = score_candidate(
        ReportedWorker(name="Ravi", trade="mason"),
        WorkerCandidate("w1", "Ravi", trade="mason", seen_on_site=True),
    )
    on_project = score_candidate(
        ReportedWorker(name="Ravi", trade="mason"),
        WorkerCandidate("w2", "Ravi", trade="mason", seen_on_project=True),
    )
    assert on_site.confidence > on_project.confidence


def test_a_trade_change_is_flagged_and_capped():
    """The duplicate screen words its question differently for "same worker,
    new trade?" than for "which of these?"."""
    scored = score_candidate(
        ReportedWorker(name="Ravi", trade="Mason"),
        WorkerCandidate("w1", "Ravi", trade="helper", seen_on_site=True),
    )
    from mesiri.domains.workforce.matching import AUTO_ACCEPT

    assert scored.trade_changed is True
    assert scored.confidence < AUTO_ACCEPT


def test_trade_change_reason_names_both_trades():
    scored = score_candidate(
        ReportedWorker(name="Ravi", trade="carpenter"),
        WorkerCandidate("w1", "Ravi", trade="mason"),
    )
    joined = " ".join(scored.reasons).lower()
    assert "mason" in joined
    assert "carpenter" in joined


def test_scored_candidates_explain_themselves():
    """These reasons are shown to the user, and they are what makes a wrong
    suggestion noticeable before it is accepted."""
    scored = score_candidate(
        ReportedWorker(name="Ravi", trade="mason", contractor="ABC"),
        WorkerCandidate("w1", "Ravi", trade="mason", contractor="ABC", seen_on_site=True),
    )
    joined = " ".join(scored.reasons).lower()
    assert "name" in joined
    assert "trade" in joined
    assert "contractor" in joined
    assert "site" in joined


def test_a_partial_name_scores_below_an_exact_one():
    exact = score_candidate(
        ReportedWorker(name="Ravi Kumar"), WorkerCandidate("w1", "Ravi Kumar")
    )
    partial = score_candidate(ReportedWorker(name="Ravi"), WorkerCandidate("w1", "Ravi Kumar"))
    assert partial.confidence < exact.confidence


def test_names_sharing_nothing_score_zero():
    scored = score_candidate(ReportedWorker(name="Ravi"), WorkerCandidate("w1", "Mahesh"))
    assert scored.confidence == 0.0


def test_an_empty_reported_name_scores_nothing():
    assert score_candidate(ReportedWorker(name=""), WorkerCandidate("w1", "Ravi")).confidence == 0.0


def test_a_missing_trade_does_not_penalise_the_score():
    """A report that omits trade is normal -- it should simply not
    corroborate, rather than counting against the match."""
    scored = score_candidate(
        ReportedWorker(name="Ravi"), WorkerCandidate("w1", "Ravi", trade="mason")
    )
    assert scored.confidence > 0.0
