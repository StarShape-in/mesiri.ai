"""Contract tests for CanonicalEvent.v1.

CanonicalEvent is the normalized business-intent signal between Context (M4)
and Planner (M5). Per the architecture's layer-ownership table it must never
carry AI-provider or confidence-score knowledge — ``completeness`` is a
business-level judgement instead, which is why ``extra_field_forbidden``
specifically tries (and must fail) to smuggle a ``confidence_level`` field in.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from pydantic import ValidationError

from mesiri_contracts.assistant.canonical_event import (
    CONTRACT_VERSION,
    CanonicalEvent,
    CanonicalEventType,
    IntentCompleteness,
)

REPO = pathlib.Path(__file__).resolve().parents[3]
FIXTURES = REPO / "scenarios" / "contracts" / "canonical_event"
VALID = sorted((FIXTURES / "valid").glob("*.json"))
INVALID = sorted((FIXTURES / "invalid").glob("*.json"))


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Version constant
# ---------------------------------------------------------------------------


def test_contract_version_constant():
    assert CONTRACT_VERSION == "v1"


# ---------------------------------------------------------------------------
# CanonicalEvent.v1
# ---------------------------------------------------------------------------


def test_canonical_event_round_trip_serialization():
    event = CanonicalEvent(
        event_id="evt_test",
        correlation_id="cor_test",
        source_message_id="msg_test",
        event_type=CanonicalEventType.MATERIAL_RECEIPT_REQUESTED,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id="org_001",
        user_id="usr_001",
        project_id="prj_001",
        site_id="site_001",
        permissions=["material.record"],
        fields={"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    dumped = event.model_dump(mode="json")
    assert dumped["version"] == "v1"
    assert dumped["event_type"] == "MaterialReceiptRequested"
    assert dumped["completeness"] == "actionable"
    restored = CanonicalEvent.model_validate(dumped)
    assert restored == event


def test_canonical_event_minimal_fields():
    """Only the required fields (event_id, correlation_id, source_message_id,
    event_type, completeness, organization_id, user_id)."""
    event = CanonicalEvent(
        event_id="evt_min",
        correlation_id="cor_min",
        source_message_id="msg_min",
        event_type=CanonicalEventType.GENERAL_QUESTION_ASKED,
        completeness=IntentCompleteness.NOT_ACTIONABLE,
        organization_id="org_001",
        user_id="usr_001",
    )
    assert event.project_id is None
    assert event.site_id is None
    assert event.fields == {}
    assert event.missing_fields == []
    assert event.permissions == []


def test_canonical_event_extra_field_forbidden():
    """CanonicalEvent must never carry AI confidence scores (layer-ownership rule)."""
    with pytest.raises(ValidationError):
        CanonicalEvent.model_validate(
            {
                "event_id": "evt_test",
                "correlation_id": "cor_test",
                "source_message_id": "msg_test",
                "event_type": "ExpenseRequested",
                "completeness": "actionable",
                "organization_id": "org_001",
                "user_id": "usr_001",
                "confidence_level": "high",
            }
        )


def test_invalid_event_type_enum_rejected():
    with pytest.raises(ValidationError):
        CanonicalEvent.model_validate(
            {
                "event_id": "evt_test",
                "correlation_id": "cor_test",
                "source_message_id": "msg_test",
                "event_type": "SomethingMadeUp",
                "completeness": "actionable",
                "organization_id": "org_001",
                "user_id": "usr_001",
            }
        )


def test_invalid_completeness_enum_rejected():
    with pytest.raises(ValidationError):
        CanonicalEvent.model_validate(
            {
                "event_id": "evt_test",
                "correlation_id": "cor_test",
                "source_message_id": "msg_test",
                "event_type": "ExpenseRequested",
                "completeness": "super_confident",
                "organization_id": "org_001",
                "user_id": "usr_001",
            }
        )


def test_required_organization_id():
    with pytest.raises(ValidationError):
        CanonicalEvent.model_validate(
            {
                "event_id": "evt_test",
                "correlation_id": "cor_test",
                "source_message_id": "msg_test",
                "event_type": "ExpenseRequested",
                "completeness": "actionable",
                "user_id": "usr_001",
            }
        )


def test_required_event_type():
    with pytest.raises(ValidationError):
        CanonicalEvent.model_validate(
            {
                "event_id": "evt_test",
                "correlation_id": "cor_test",
                "source_message_id": "msg_test",
                "completeness": "actionable",
                "organization_id": "org_001",
                "user_id": "usr_001",
            }
        )


# ---------------------------------------------------------------------------
# Fixture-driven contract tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_valid_fixtures_parse(path: pathlib.Path) -> None:
    event = CanonicalEvent.model_validate(_load(path))
    assert event.version == CONTRACT_VERSION
    assert event.correlation_id
    assert event.source_message_id
    assert event.organization_id
    assert event.user_id
    assert isinstance(event.event_type, CanonicalEventType)
    assert isinstance(event.completeness, IntentCompleteness)


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_invalid_fixtures_are_rejected(path: pathlib.Path) -> None:
    with pytest.raises(ValidationError):
        CanonicalEvent.model_validate(_load(path))
