"""workflows/site_update/matching.py -- unit tests.

Fixes F1 (wrong target) and F2 (dead end) from
docs/execution/ACTIVITY_RESOLUTION_AND_CORRECTION_PLAN.md. See
test_seed_open_activity.py / test_activity_continuation_nodes.py for the
characterization of the old (buggy) recency-only behaviour this replaces.
"""

from __future__ import annotations

from workflows.site_update.matching import (
    ActivityCandidate,
    MatchOutcome,
    resolve_target,
)

PLASTERING = ActivityCandidate(activity_id="p1", work_type="plastering", narrative="2nd floor")
BLOCKWORK = ActivityCandidate(activity_id="b1", work_type="blockwork", narrative="Block A")
UNTYPED = ActivityCandidate(activity_id="u1", work_type=None, narrative="misc")


def test_f2_no_candidates_creates_new_with_no_question():
    result = resolve_target(message_work_type=None, update_kind="completed", candidates=[])
    assert result.outcome is MatchOutcome.NO_MATCH
    assert result.matched_activity_id is None


def test_f1_exact_work_type_match_wins_even_with_a_more_recent_clashing_candidate():
    """The actual F1 scenario: "finished plastering" with plastering AND
    blockwork both open. The old code picked whichever was most recently
    updated, with no regard for which one the message was about. This picks
    plastering regardless of candidate order."""
    result = resolve_target(
        message_work_type="plastering",
        update_kind="completed",
        candidates=[BLOCKWORK, PLASTERING],
    )
    assert result.outcome is MatchOutcome.AUTO_MATCHED
    assert result.matched_activity_id == "p1"


def test_clash_with_the_only_open_activity_asks_instead_of_appending_to_it():
    """"Finished plastering" with only blockwork open. Silently appending
    would be F1 again; silently creating new could also be wrong if the
    work_type was misheard. Ask, with a "this is new work" option."""
    result = resolve_target(
        message_work_type="plastering", update_kind="completed", candidates=[BLOCKWORK]
    )
    assert result.outcome is MatchOutcome.ASK_USER
    assert result.candidates[0].clash is True


def test_single_candidate_continuation_wording_no_restated_work_type_auto_matches():
    """The single deliberate exception to "ask readily": one thing open,
    explicit continuation language, nothing to disambiguate against. Asking
    here would be pure friction -- this is the common "another 40 sqm done"
    case when conversational memory (CurrentActivityStore) didn't already
    short-circuit it upstream."""
    result = resolve_target(message_work_type=None, update_kind="progress", candidates=[PLASTERING])
    assert result.outcome is MatchOutcome.AUTO_MATCHED
    assert result.matched_activity_id == "p1"


def test_single_candidate_no_work_type_and_no_continuation_hint_asks():
    """No signal at all which way this goes -- e.g. update_kind was omitted
    by extraction entirely (F3's old trigger). Must ask rather than default
    to either "always continue" or "always create"."""
    result = resolve_target(message_work_type=None, update_kind=None, candidates=[PLASTERING])
    assert result.outcome is MatchOutcome.ASK_USER


def test_multiple_untyped_candidates_with_continuation_hint_asks():
    """Continuation wording alone never picks between two open jobs -- the
    single-candidate shortcut requires exactly one candidate."""
    result = resolve_target(
        message_work_type=None, update_kind="progress", candidates=[PLASTERING, BLOCKWORK]
    )
    assert result.outcome is MatchOutcome.ASK_USER


def test_message_names_a_work_type_matching_no_open_candidate_asks_not_creates():
    """A stated work_type that matches nothing open is still a clash against
    every candidate (score 0.1 each) -- ask, don't silently create, since
    the message clearly believes something is already in progress."""
    result = resolve_target(
        message_work_type="tiling", update_kind="completed", candidates=[PLASTERING, BLOCKWORK]
    )
    assert result.outcome is MatchOutcome.ASK_USER
    assert all(c.clash for c in result.candidates)


def test_candidate_with_no_recorded_work_type_is_neutral_not_a_clash():
    result = resolve_target(
        message_work_type="plastering", update_kind="completed", candidates=[UNTYPED]
    )
    assert result.outcome is MatchOutcome.ASK_USER
    assert result.candidates[0].clash is False


def test_candidates_are_returned_best_first():
    result = resolve_target(
        message_work_type="plastering", update_kind=None, candidates=[BLOCKWORK, PLASTERING]
    )
    assert result.candidates[0].activity_id == "p1"
    assert result.candidates[1].activity_id == "b1"
