"""DecompositionResult's self-normalization
(docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §9): fewer than two non-blank
segments is never a real split, whatever ``is_multi_intent`` claims. Enforced
once, on the model, rather than duplicated in every adapter that constructs
one.
"""

from __future__ import annotations

from mesiri_ai.models import DecompositionResult


def test_default_is_not_multi_intent():
    result = DecompositionResult()
    assert result.is_multi_intent is False
    assert result.segments == []


def test_two_real_segments_with_is_multi_intent_true_is_accepted_as_is():
    result = DecompositionResult(
        is_multi_intent=True,
        segments=["create a project called Starship", "create a site called Site A"],
    )
    assert result.is_multi_intent is True
    assert result.segments == [
        "create a project called Starship",
        "create a site called Site A",
    ]


def test_is_multi_intent_true_with_only_one_segment_is_forced_false():
    """A provider hallucinating "yes, split" with one element must not turn
    an ordinary single-intent message into a pointless one-step "plan"."""
    result = DecompositionResult(is_multi_intent=True, segments=["only one thing"])
    assert result.is_multi_intent is False
    assert result.segments == []


def test_is_multi_intent_true_with_an_empty_list_is_forced_false():
    result = DecompositionResult(is_multi_intent=True, segments=[])
    assert result.is_multi_intent is False
    assert result.segments == []


def test_blank_segments_are_stripped_before_counting():
    """Two segments where one is whitespace-only is really one segment."""
    result = DecompositionResult(is_multi_intent=True, segments=["real segment", "   "])
    assert result.is_multi_intent is False
    assert result.segments == []


def test_is_multi_intent_false_clears_any_segments_a_provider_still_sent():
    """The is_multi_intent flag is authoritative -- segments sent alongside
    a false flag must never leak through and be mistaken for a real split."""
    result = DecompositionResult(is_multi_intent=False, segments=["a", "b", "c"])
    assert result.is_multi_intent is False
    assert result.segments == []


def test_three_real_segments_preserve_original_order():
    """Order is never re-derived here -- planning/ordering.py derives
    dependency order later, from each segment's own extraction."""
    segments = ["create project Starship", "create site Site A", "create user Hysam"]
    result = DecompositionResult(is_multi_intent=True, segments=segments)
    assert result.segments == segments
