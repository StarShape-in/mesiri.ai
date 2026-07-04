"""Confidence policy is deterministic and independently testable (M3)."""


from mesiri_ai.confidence import ConfidencePolicy, ConfidenceSignals
from mesiri_contracts.assistant.confidence import ConfidenceLevel

policy = ConfidencePolicy()


def test_provider_failure_is_unusable():
    assert policy.evaluate(ConfidenceSignals(provider_succeeded=False)) == ConfidenceLevel.UNUSABLE


def test_invalid_schema_is_unusable():
    assert policy.evaluate(ConfidenceSignals(schema_valid=False)) == ConfidenceLevel.UNUSABLE


def test_empty_content_is_unusable():
    assert policy.evaluate(ConfidenceSignals(is_empty=True)) == ConfidenceLevel.UNUSABLE


def test_required_field_missing_is_low():
    sig = ConfidenceSignals(
        required_fields=("amount",),
        present_fields=(),
        field_confidences=(0.9,),
    )
    assert policy.evaluate(sig) == ConfidenceLevel.LOW


def test_ambiguous_is_low():
    sig = ConfidenceSignals(
        required_fields=("amount",),
        present_fields=("amount",),
        field_confidences=(0.9,),
        ambiguous=True,
    )
    assert policy.evaluate(sig) == ConfidenceLevel.LOW


def test_optional_missing_is_medium():
    sig = ConfidenceSignals(
        required_fields=("amount",),
        present_fields=("amount",),
        missing_fields=("vendor",),
        field_confidences=(0.9, 0.85),
    )
    assert policy.evaluate(sig) == ConfidenceLevel.MEDIUM


def test_all_present_high_confidence_is_high():
    sig = ConfidenceSignals(
        required_fields=("equipment_name", "duration_hours"),
        present_fields=("equipment_name", "duration_hours"),
        field_confidences=(0.97, 0.95),
    )
    assert policy.evaluate(sig) == ConfidenceLevel.HIGH


def test_is_deterministic():
    sig = ConfidenceSignals(
        required_fields=("amount",), present_fields=("amount",), field_confidences=(0.8,)
    )
    assert len({policy.evaluate(sig) for _ in range(20)}) == 1


def test_confidence_level_rank_ordering():
    assert ConfidenceLevel.HIGH.rank > ConfidenceLevel.MEDIUM.rank
    assert ConfidenceLevel.MEDIUM.rank > ConfidenceLevel.LOW.rank
    assert ConfidenceLevel.LOW.rank > ConfidenceLevel.UNUSABLE.rank
