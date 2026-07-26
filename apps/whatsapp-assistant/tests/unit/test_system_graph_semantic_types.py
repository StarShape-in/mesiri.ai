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
        "MaterialReceiptRequested",
        "MaterialUsageRequested",
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
    # labour_update joined this list when the Labour attendance graph was
    # registered (Labour plan Phase 3) -- the System Graph derives
    # `implemented` live from _BUILDERS, so it now shows labour.attendance as
    # built rather than "not built yet".
    assert infos["labour_update"].implemented is True
    # Routed but not built yet.
    for name in ("equipment_usage", "general_site_update"):
        assert infos[name].implemented is False
        assert infos[name].workflow_keys  # still mapped to a (future) workflow


def test_simulate_models_support_interactive_payloads() -> None:
    import uuid

    from admin.system_graph_router import (
        ReplyOptionInfo,
        SimulateRequest,
        SimulateResponse,
        StructuredReplyInfo,
    )

    req = SimulateRequest(
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        text="Confirm",
        modality="interactive",
        interactive_reply_id="confirm",
    )
    assert req.modality == "interactive"
    assert req.interactive_reply_id == "confirm"

    resp = SimulateResponse(
        dry_run=True,
        ran_as_wa_id="12345",
        routed_via="confirmation_fast_path",
        replies=["Confirmed"],
        structured_replies=[
            StructuredReplyInfo(
                type="buttons",
                text="Confirm?",
                buttons=[ReplyOptionInfo(id="confirm", title="Yes")],
            )
        ],
    )
    assert resp.structured_replies[0].type == "buttons"
    assert resp.structured_replies[0].buttons[0].id == "confirm"

