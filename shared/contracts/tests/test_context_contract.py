"""Contract tests for ResolvedContext.v1 and context port DTOs."""

from __future__ import annotations

import json
import pathlib

import pytest
from pydantic import ValidationError

from mesiri_contracts.assistant.confidence import ConfidenceLevel
from mesiri_contracts.context import (
    CONTRACT_VERSION,
    ActiveWorkflowSnapshot,
    ActorContext,
    ContextAmbiguity,
    ContextAmbiguityField,
    IdentityLookupPort,
    IdentityRecord,
    InteractionContext,
    InteractionKind,
    PendingInteractionSnapshot,
    ReplyBindingContext,
    ResolvedContext,
    ScopeContext,
    ScopeLookupPort,
    ScopeRecord,
    UserRole,
    WorkflowContext,
    WorkflowKind,
    WorkflowPhase,
    WorkflowStateReadPort,
)

REPO = pathlib.Path(__file__).resolve().parents[3]
FIXTURES = REPO / "scenarios" / "contracts" / "context"
VALID = sorted((FIXTURES / "valid").glob("*.json"))
INVALID = sorted((FIXTURES / "invalid").glob("*.json"))


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_contract_version_constant():
    assert CONTRACT_VERSION == "v1"


def test_resolved_context_round_trip_serialization():
    ctx = ResolvedContext(
        correlation_id="cor_test",
        source_message_id="msg_test",
        actor=ActorContext(
            whatsapp_wa_id="919876543210",
            user_id="usr_1",
            organization_id="org_1",
            role=UserRole.SITE_ENGINEER,
            display_name="Engineer",
        ),
        scope=ScopeContext(
            project_id="prj_1",
            project_name="Tower A",
            site_id="site_1",
            site_name="Block 3",
        ),
        workflow=WorkflowContext(
            workflow_instance_id="wf_1",
            workflow_kind=WorkflowKind.MATERIAL,
            phase=WorkflowPhase.AWAITING_CONFIRMATION,
        ),
        interaction=InteractionContext(
            interaction_id="int_1",
            kind=InteractionKind.CONFIRMATION,
            related_message_id="msg_prior",
        ),
        reply=ReplyBindingContext(
            replied_to_message_id="msg_prior",
            binds_to_prior_journey=True,
        ),
        confidence=ConfidenceLevel.HIGH,
        ambiguities=[
            ContextAmbiguity(
                field=ContextAmbiguityField.SITE,
                reason="multiple sites matched",
                candidates=["site_1", "site_2"],
            )
        ],
        warnings=["example"],
        resolved_at="2026-07-06T12:00:00Z",
    )
    dumped = ctx.model_dump(mode="json")
    assert dumped["version"] == "v1"
    restored = ResolvedContext.model_validate(dumped)
    assert restored == ctx


def test_port_dtos_use_enums_and_forbid_extra_fields():
    identity = IdentityRecord(
        user_id="usr_1",
        organization_id="org_1",
        role=UserRole.SITE_ENGINEER,
        whatsapp_wa_id="919876543210",
    )
    assert identity.role is UserRole.SITE_ENGINEER

    with pytest.raises(ValidationError):
        IdentityRecord.model_validate(
            {
                "user_id": "usr_1",
                "role": "worker",
                "whatsapp_wa_id": "919876543210",
                "unexpected": True,
            }
        )

    workflow = ActiveWorkflowSnapshot(
        workflow_instance_id="wf_1",
        workflow_kind=WorkflowKind.EXPENSE,
        phase=WorkflowPhase.PAUSED,
    )
    assert workflow.phase is WorkflowPhase.PAUSED

    interaction = PendingInteractionSnapshot(
        interaction_id="int_1",
        kind=InteractionKind.MISSING_FIELD,
    )
    assert interaction.kind is InteractionKind.MISSING_FIELD

    scope = ScopeRecord(project_id="prj_1", site_id="site_1")
    assert scope.project_id == "prj_1"


def test_context_ports_are_runtime_checkable_protocols():
    class _Identity:
        async def resolve_by_whatsapp(self, wa_id: str, *, correlation_id: str) -> IdentityRecord | None:
            return None

    class _Scope:
        async def resolve_default_scope(
            self, user_id: str, organization_id: str, *, correlation_id: str
        ) -> ScopeRecord | None:
            return None

        async def resolve_by_reply(
            self, replied_to_message_id: str, *, correlation_id: str
        ) -> ScopeRecord | None:
            return None

    class _WorkflowState:
        async def get_active_workflow(
            self, user_id: str, *, correlation_id: str
        ) -> ActiveWorkflowSnapshot | None:
            return None

        async def get_pending_interaction(
            self, user_id: str, *, correlation_id: str
        ) -> PendingInteractionSnapshot | None:
            return None

    assert isinstance(_Identity(), IdentityLookupPort)
    assert isinstance(_Scope(), ScopeLookupPort)
    assert isinstance(_WorkflowState(), WorkflowStateReadPort)


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_valid_fixtures_parse(path: pathlib.Path) -> None:
    ctx = ResolvedContext.model_validate(_load(path))
    assert ctx.version == CONTRACT_VERSION
    assert ctx.correlation_id
    assert ctx.source_message_id
    assert ctx.actor.whatsapp_wa_id
    assert isinstance(ctx.confidence, ConfidenceLevel)


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_invalid_fixtures_are_rejected(path: pathlib.Path) -> None:
    with pytest.raises(ValidationError):
        ResolvedContext.model_validate(_load(path))


def test_invalid_confidence_enum_rejected():
    payload = _load(VALID[0])
    payload["confidence"] = "certainly_high"
    with pytest.raises(ValidationError):
        ResolvedContext.model_validate(payload)


def test_required_actor_whatsapp_wa_id():
    payload = _load(VALID[0])
    del payload["actor"]["whatsapp_wa_id"]
    with pytest.raises(ValidationError):
        ResolvedContext.model_validate(payload)
