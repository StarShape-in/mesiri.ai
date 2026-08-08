"""Contract tests for ResolvedContext.v1 (M4 flat schema) and context port DTOs.

``ResolvedContext`` is imported from ``mesiri_contracts.assistant.resolved_context``
(the canonical M4 flat schema).  The nested schema that previously lived in
``mesiri_contracts.context.resolved_context`` has been retired — see Phase 0 T4.

The port DTOs and enumerations (``IdentityLookupPort``, ``UserRole``, etc.) remain
in ``mesiri_contracts.context`` and are tested here alongside the contract.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from pydantic import ValidationError

from mesiri_contracts.assistant.context_enums import ContextConfidence, ContextSource
from mesiri_contracts.assistant.resolved_context import CONTRACT_VERSION, ResolvedContext
from mesiri_contracts.context import (
    ActiveWorkflowSnapshot,
    ContextAmbiguityField,
    IdentityLookupPort,
    IdentityRecord,
    InteractionKind,
    PendingInteractionSnapshot,
    ScopeLookupPort,
    ScopeRecord,
    UserRole,
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


# ---------------------------------------------------------------------------
# Version constant
# ---------------------------------------------------------------------------


def test_contract_version_constant():
    assert CONTRACT_VERSION == "v1"


# ---------------------------------------------------------------------------
# ResolvedContext.v1 — M4 flat schema
# ---------------------------------------------------------------------------


def test_resolved_context_round_trip_serialization():
    ctx = ResolvedContext(
        correlation_id="cor_test",
        source_message_id="msg_test",
        organization_id="org_001",
        user_id="usr_001",
        membership_id="mbr_001",
        role_ids=["site_engineer"],
        permissions=["material.record"],
        project_id="prj_001",
        site_id="site_001",
        context_source=ContextSource.USER_DEFAULT,
        context_confidence=ContextConfidence.HIGH,
        locale="en",
        timezone="Asia/Kolkata",
    )
    dumped = ctx.model_dump(mode="json")
    assert dumped["version"] == "v1"
    assert dumped["organization_id"] == "org_001"
    assert dumped["user_id"] == "usr_001"
    assert dumped["context_confidence"] == "high"
    restored = ResolvedContext.model_validate(dumped)
    assert restored == ctx


def test_resolved_context_minimal_fields():
    """Only the required fields (correlation_id, source_message_id, org, user)."""
    ctx = ResolvedContext(
        correlation_id="cor_min",
        source_message_id="msg_min",
        organization_id="org_001",
        user_id="usr_001",
    )
    assert ctx.context_confidence is ContextConfidence.UNRESOLVED
    assert ctx.context_source is ContextSource.UNRESOLVED
    assert ctx.project_id is None
    assert ctx.site_id is None


def test_resolved_context_extra_field_forbidden():
    with pytest.raises(ValidationError):
        ResolvedContext.model_validate(
            {
                "correlation_id": "cor_test",
                "source_message_id": "msg_test",
                "organization_id": "org_001",
                "user_id": "usr_001",
                "planner_decision": "must_not_appear_on_context_contract",
            }
        )


def test_invalid_context_confidence_enum_rejected():
    with pytest.raises(ValidationError):
        ResolvedContext.model_validate(
            {
                "correlation_id": "cor_test",
                "source_message_id": "msg_test",
                "organization_id": "org_001",
                "user_id": "usr_001",
                "context_confidence": "certainly_high",
            }
        )


def test_required_user_id():
    with pytest.raises(ValidationError):
        ResolvedContext.model_validate(
            {
                "correlation_id": "cor_test",
                "source_message_id": "msg_test",
                "organization_id": "org_001",
            }
        )


def test_required_organization_id():
    with pytest.raises(ValidationError):
        ResolvedContext.model_validate(
            {
                "correlation_id": "cor_test",
                "source_message_id": "msg_test",
                "user_id": "usr_001",
            }
        )


# ---------------------------------------------------------------------------
# Fixture-driven contract tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_valid_fixtures_parse(path: pathlib.Path) -> None:
    ctx = ResolvedContext.model_validate(_load(path))
    assert ctx.version == CONTRACT_VERSION
    assert ctx.correlation_id
    assert ctx.source_message_id
    assert ctx.organization_id
    assert ctx.user_id
    assert isinstance(ctx.context_confidence, ContextConfidence)


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_invalid_fixtures_are_rejected(path: pathlib.Path) -> None:
    with pytest.raises(ValidationError):
        ResolvedContext.model_validate(_load(path))


# ---------------------------------------------------------------------------
# Port DTOs and enumerations (mesiri_contracts.context)
# ---------------------------------------------------------------------------


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
        async def resolve_by_whatsapp(
            self, wa_id: str, *, correlation_id: str
        ) -> IdentityRecord | None:
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


def test_user_role_enum_contains_canonical_mesiri_roles():
    assert UserRole.OWNER.value == "owner"
    assert UserRole.PROJECT_MANAGER.value == "project_manager"
    assert UserRole.SITE_ENGINEER.value == "site_engineer"
    assert UserRole.ACCOUNTANT.value == "accountant"


def test_context_ambiguity_field_enum():
    assert ContextAmbiguityField.PROJECT.value == "project"
    assert ContextAmbiguityField.SITE.value == "site"
