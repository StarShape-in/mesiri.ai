"""Deterministic confidence policy (M3).

Maps objective signals about an extraction to a :class:`ConfidenceLevel`. The
policy is pure and independently testable — given the same signals it always
returns the same level. It only *classifies*; it never decides interaction
behavior (clarification etc.), which is downstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mesiri_contracts.assistant.confidence import ConfidenceLevel

# Thresholds on average per-field confidence [0, 1].
_HIGH_MIN = 0.75
_MEDIUM_MIN = 0.45


@dataclass(frozen=True)
class ConfidenceSignals:
    provider_succeeded: bool = True
    schema_valid: bool = True
    is_empty: bool = False  # e.g. empty transcript / no content
    required_fields: tuple[str, ...] = ()
    present_fields: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    field_confidences: tuple[float, ...] = field(default_factory=tuple)
    ambiguous: bool = False

    @property
    def average_confidence(self) -> float:
        if not self.field_confidences:
            return 0.0
        return sum(self.field_confidences) / len(self.field_confidences)

    @property
    def required_missing(self) -> tuple[str, ...]:
        present = set(self.present_fields)
        return tuple(f for f in self.required_fields if f not in present)


class ConfidencePolicy:
    """Stateless evaluator — deterministic classification of extraction quality."""

    def evaluate(self, signals: ConfidenceSignals) -> ConfidenceLevel:
        # Hard failures -> unusable.
        if not signals.provider_succeeded or not signals.schema_valid or signals.is_empty:
            return ConfidenceLevel.UNUSABLE

        avg = signals.average_confidence

        # Required data missing, ambiguity, or very low signal -> low.
        if signals.required_missing or signals.ambiguous or avg < _MEDIUM_MIN:
            return ConfidenceLevel.LOW

        # Optional data missing or middling signal -> medium.
        if signals.missing_fields or avg < _HIGH_MIN:
            return ConfidenceLevel.MEDIUM

        return ConfidenceLevel.HIGH
