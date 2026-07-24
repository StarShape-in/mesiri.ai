"""The System Graph's semantic-type catalog is derived live from the routing
tables, so these assert the derivation stays honest: every SemanticType is
present, MATERIAL_UPDATE fans out to both material workflows, and the
direct-reply types (GENERAL_QUESTION / UNKNOWN) never claim a workflow."""

from __future__ import annotations

from admin.system_graph_router import _semantic_type_infos
from mesiri_contracts.assistant.enums import SemanticType


def _by_type() -> dict[str, object]:
    return {info.semantic_type: info for info in _semantic_type_infos()}


def test_every_semantic_type_is_catalogued() -> None:
    catalogued = {info.semantic_type for info in _semantic_type_infos()}
    assert catalogued == {s.value for s in SemanticType}


def test_material_update_fans_out_to_both_material_workflows() -> None:
    info = _by_type()["material_update"]
    assert info.workflow_keys == ["material.receipt", "material.usage"]
    assert info.canonical_events == [
        "material_receipt_requested",
        "material_usage_requested",
    ]
    assert info.implemented is True


def test_direct_reply_types_have_no_workflow() -> None:
    infos = _by_type()
    for name in ("general_question", "unknown"):
        info = infos[name]
        assert info.workflow_keys == []
        assert info.implemented is False
        assert info.routes_to_reply  # a human note explaining the direct reply


def test_built_vs_unbuilt_matches_the_registry() -> None:
    infos = _by_type()
    # Built today (in workflows.registry._BUILDERS).
    assert infos["expense"].implemented is True
    assert infos["inventory_query"].implemented is True
    assert infos["whoami_question"].implemented is True
    # Routed but not built yet.
    for name in ("equipment_usage", "labour_update", "general_site_update"):
        assert infos[name].implemented is False
        assert infos[name].workflow_keys  # still mapped to a (future) workflow
