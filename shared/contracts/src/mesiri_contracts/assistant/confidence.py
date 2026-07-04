"""Confidence levels for understanding results (M3).

A coarse, ordered classification derived deterministically from provider signals
and schema validity (see ``mesiri_ai.confidence``). Downstream layers decide what
to *do* with each level (e.g. clarification) — that behavior is out of M3 scope.

Ownership: Ilan (part of UnderstandingResult.v1).
"""

from __future__ import annotations

from enum import Enum


class ConfidenceLevel(str, Enum):
    HIGH = "high"          # ready for downstream use as-is
    MEDIUM = "medium"      # usable but some required fields uncertain/missing
    LOW = "low"            # significant ambiguity or missing required fields
    UNUSABLE = "unusable"  # cannot be acted upon (empty / malformed / failed)

    @property
    def rank(self) -> int:
        return {"unusable": 0, "low": 1, "medium": 2, "high": 3}[self.value]
