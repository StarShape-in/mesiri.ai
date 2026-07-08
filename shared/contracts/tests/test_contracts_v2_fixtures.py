"""Contract fixture tests for assistant v2 contracts."""

from __future__ import annotations

import json
import pathlib

import pytest
from pydantic import ValidationError

from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2

REPO = pathlib.Path(__file__).resolve().parents[3]

_MODELS = {
    "context": ResolvedContextV2,
    "canonical_event": CanonicalEventV2,
    "planner_decision": PlannerDecisionV2,
    "workflow_state": WorkflowStateV2,
    "draft_action": DraftActionV2,
}


def _fixture_paths(contract: str, kind: str) -> list[pathlib.Path]:
    return sorted((REPO / "scenarios" / "contracts" / contract / "v2" / kind).glob("*.json"))


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("contract", list(_MODELS))
def test_v2_valid_fixtures_parse(contract: str) -> None:
    model = _MODELS[contract]
    paths = _fixture_paths(contract, "valid")
    assert paths, f"no v2 valid fixtures for {contract}"
    for path in paths:
        obj = model.model_validate(_load(path))
        assert obj.version == "v2"


@pytest.mark.parametrize("contract", list(_MODELS))
def test_v2_invalid_fixtures_rejected(contract: str) -> None:
    model = _MODELS[contract]
    paths = _fixture_paths(contract, "invalid")
    assert paths, f"no v2 invalid fixtures for {contract}"
    for path in paths:
        with pytest.raises(ValidationError):
            model.model_validate(_load(path))
