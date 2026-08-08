"""Entity resolution -- turning a free-text name hint into a real row, or
knowing honestly that it isn't one yet (docs/execution/ENTITY_RESOLUTION_PLAN.md).

Split from workflows/entities.py (the pure vocabulary: EntityType,
Resolved/Ambiguous/Missing) the same way understanding/ is split from
canonicalization/ -- this package does the I/O and the scoring; entities.py
stays pure so it can be imported from workflows/registry.py without pulling
a database dependency into the registry.
"""

from __future__ import annotations


def normalize_name(name: str) -> str:
    """The one rule for "are these two names the same name?" -- shared by
    every resolver in this package so USER and MATERIAL cannot drift apart on
    what counts as an exact match (case, and runs of whitespace, are noise;
    nothing else is).

    Deliberately not a general slugifier: it must never strip punctuation or
    fold accents, because those genuinely distinguish real catalog entries
    ("M-Sand" vs "M Sand" are plausibly two rows an org created on purpose,
    and deciding they are the same is not this function's call to make).
    """
    return " ".join(name.strip().lower().split())
