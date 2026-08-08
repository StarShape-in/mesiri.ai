"""Person-like name resolution -- unit tests (pure scoring, no DB).

Covers the live bug (ENTITY_RESOLUTION_PLAN.md §1: ഹൈസം / "Hysam" against an
org where the real user is "Hisham") and the false-merge risk
workforce/matching.py's match_worker explicitly rejects fuzzy matching over
(Sunil/Sunita, Ramesh/Rakesh) -- proving those pairs land in Ambiguous
(always asks), never Resolved (never silently merges).

The scorer moved to name_matching.py in Phase 4 when VENDOR became its
second caller; these tests moved with it (they never touched the member
wiring, only the scoring). Vendor-specific coverage lives in
test_vendor_resolution.py.
"""

from __future__ import annotations

from runtime.entity_resolution.name_matching import (
    NamedCandidate,
    resolve_name_hint,
)
from workflows.entities import Ambiguous, Missing, Resolved


def _candidates(*names: str) -> list[NamedCandidate]:
    return [NamedCandidate(entity_id=f"u_{i}", display_name=n) for i, n in enumerate(names)]


def test_exact_match_wins_outright_case_insensitive():
    result = resolve_name_hint("hisham", _candidates("Hisham", "Someone Else"))
    assert isinstance(result, Resolved)
    assert result.entity_id == "u_0"
    assert result.display_name == "Hisham"


def test_exact_match_ignores_surrounding_whitespace():
    result = resolve_name_hint("  Hisham  ", _candidates("Hisham"))
    assert isinstance(result, Resolved)


def test_the_live_bug_transliteration_case_becomes_ambiguous_not_missing():
    """The actual reported failure: ഹൈസം transliterates as "Hysam"; the real
    user is registered as "Hisham". This must surface as a pickable
    candidate, not the old dead-end "couldn't find an active user"."""
    result = resolve_name_hint("Hysam", _candidates("Hisham", "Rajesh Kumar"))
    assert isinstance(result, Ambiguous)
    assert result.candidates[0].display_name == "Hisham"


def test_lookalike_names_are_ambiguous_never_silently_resolved():
    """match_worker's docstring rejects fuzzy matching specifically because
    Sunil/Sunita and Ramesh/Rakesh are DIFFERENT real people who happen to
    look similar. This module must never silently merge them -- a
    high-scoring look-alike is Ambiguous (always asks), never Resolved."""
    for reported, registered in [("Sunil", "Sunita"), ("Ramesh", "Rakesh")]:
        result = resolve_name_hint(reported, _candidates(registered))
        assert isinstance(result, Ambiguous), f"{reported!r} vs {registered!r} must ask, not merge"


def test_no_close_candidate_is_missing_not_a_bad_guess():
    result = resolve_name_hint("Hysam", _candidates("Completely Unrelated Person"))
    assert isinstance(result, Missing)
    assert result.name_hint == "Hysam"


def test_missing_carries_the_original_name_hint_verbatim():
    """So the caller can offer to create a user with exactly this name --
    never a normalized or mangled version (ADR-E4)."""
    result = resolve_name_hint("  Hysam  ", _candidates())
    assert isinstance(result, Missing)
    assert result.name_hint == "  Hysam  "


def test_empty_name_hint_is_missing_not_a_crash():
    result = resolve_name_hint("", _candidates("Hisham"))
    assert isinstance(result, Missing)


def test_no_candidates_at_all_is_missing():
    result = resolve_name_hint("Hysam", [])
    assert isinstance(result, Missing)


def test_ambiguous_candidates_are_ordered_best_match_first():
    result = resolve_name_hint(
        "Rajesh Kumar",
        _candidates("Rajesh K", "Raj Kumar", "Totally Different"),
    )
    assert isinstance(result, Ambiguous)
    names = [c.display_name for c in result.candidates]
    assert "Totally Different" not in names
    # Both partial matches present, closer one first.
    assert names[0] in ("Rajesh K", "Raj Kumar")


def test_ambiguous_candidates_are_capped():
    # Single-character variations on the same short name -- all genuinely
    # close matches, unlike a name embedded in a much longer string (which
    # SequenceMatcher correctly scores low regardless of cap behaviour).
    many = _candidates("Hysam", "Hysan", "Hysab", "Hysac", "Hysad", "Hysae", "Hysaf")
    result = resolve_name_hint("Hysaa", many)
    assert isinstance(result, Ambiguous)
    assert len(result.candidates) <= 5


def test_partial_name_match_is_ambiguous():
    """"Rajesh" reported against registered "Rajesh Kumar" -- a real signal,
    same as workforce/matching.py's _W_NAME_PARTIAL case, but here it always
    asks rather than being silently accepted."""
    result = resolve_name_hint("Rajesh", _candidates("Rajesh Kumar"))
    assert isinstance(result, Ambiguous)
