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

        # A semantic type with no required fields and nothing extracted
        # (greeting, whoami, a general question) isn't "low confidence" --
        # there was nothing to be confident or uncertain about.
        # average_confidence's empty-tuple default of 0.0 would otherwise
        # score this the same as a real low-confidence extraction, which
        # would send a correctly-classified "hi" down a clarification path
        # instead of just answering it. This case used to be unreachable in
        # practice -- these semantic types were always short-circuited
        # before ever reaching this policy (see pipeline.py's deterministic
        # greeting/whoami shortcuts) -- until voice's merged
        # understand_voice() call started routing greetings through
        # ordinary extraction instead, since there's no longer a cheap
        # pre-check to skip it with.
        if (
            not signals.required_fields
            and not signals.present_fields
            and not signals.field_confidences
        ):
            return ConfidenceLevel.HIGH

        avg = signals.average_confidence

        # Required data missing, ambiguity, or very low signal -> low.
        if signals.required_missing or signals.ambiguous or avg < _MEDIUM_MIN:
            return ConfidenceLevel.LOW

        # Optional data missing or middling signal -> medium.
        if signals.missing_fields or avg < _HIGH_MIN:
            return ConfidenceLevel.MEDIUM

        return ConfidenceLevel.HIGH
