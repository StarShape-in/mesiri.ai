"""Contract tests for DraftAction.v1.

DraftAction is the workflow->application handoff produced by the Workflow
Runtime (M6): a proposed business action awaiting confirmation. Nothing is
persisted to the domain until confirmation (architecture rule #4).
"""

from __future__ import annotations

import json
import pathlib

import pytest
from pydantic import ValidationError

from mesiri_contracts.assistant.draft_action import CONTRACT_VERSION, DraftAction, DraftActionType

REPO = pathlib.Path(__file__).resolve().parents[3]
FIXTURES = REPO / "scenarios" / "contracts" / "draft_action"
VALID = sorted((FIXTURES / "valid").glob("*.json"))
INVALID = sorted((FIXTURES / "invalid").glob("*.json"))


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_contract_version_constant():
    assert CONTRACT_VERSION == "v1"


def test_draft_action_round_trip_serialization():
    draft = DraftAction(
        draft_id="draft_test",
        correlation_id="cor_test",
        causation_event_id="evt_test",
        workflow_instance_id="wf_test",
        action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
        organization_id="org_001",
        user_id="usr_001",
        project_id="prj_001",
        site_id="site_001",
        fields={"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    dumped = draft.model_dump(mode="json")
    assert dumped["version"] == "v1"
    assert dumped["action_type"] == "record_material_receipt"
    restored = DraftAction.model_validate(dumped)
    assert restored == draft


def test_draft_action_minimal_fields():
    draft = DraftAction(
        draft_id="draft_min",
        correlation_id="cor_min",
        workflow_instance_id="wf_min",
        action_type=DraftActionType.RECORD_MATERIAL_USAGE,
        organization_id="org_001",
        user_id="usr_001",
    )
    assert draft.project_id is None
    assert draft.site_id is None
    assert draft.causation_event_id is None
    assert draft.fields == {}


def test_draft_action_extra_field_forbidden():
    with pytest.raises(ValidationError):
        DraftAction.model_validate(
            {
                "draft_id": "draft_test",
                "correlation_id": "cor_test",
                "workflow_instance_id": "wf_test",
                "action_type": "record_material_receipt",
                "organization_id": "org_001",
                "user_id": "usr_001",
                "confidence_level": "high",
            }
        )


def test_invalid_action_type_enum_rejected():
    with pytest.raises(ValidationError):
        DraftAction.model_validate(
            {
                "draft_id": "draft_test",
                "correlation_id": "cor_test",
                "workflow_instance_id": "wf_test",
                "action_type": "delete_everything",
                "organization_id": "org_001",
                "user_id": "usr_001",
            }
        )


def test_required_organization_id():
    with pytest.raises(ValidationError):
        DraftAction.model_validate(
            {
                "draft_id": "draft_test",
                "correlation_id": "cor_test",
                "workflow_instance_id": "wf_test",
                "action_type": "record_material_receipt",
                "user_id": "usr_001",
            }
        )


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_valid_fixtures_parse(path: pathlib.Path) -> None:
    draft = DraftAction.model_validate(_load(path))
    assert draft.version == CONTRACT_VERSION
    assert draft.draft_id
    assert draft.correlation_id
    assert draft.workflow_instance_id
    assert isinstance(draft.action_type, DraftActionType)


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_invalid_fixtures_are_rejected(path: pathlib.Path) -> None:
    with pytest.raises(ValidationError):
        DraftAction.model_validate(_load(path))
