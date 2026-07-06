"""Unit tests for ContextResolver (fake adapters only)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from context.adapters import (
    FakeIdentityLookupPort,
    FakeScopeLookupPort,
    FakeWorkflowStateReadPort,
)
from context.contract_resolver import ContractContextResolver
from mesiri_contracts.assistant.confidence import ConfidenceLevel
from mesiri_contracts.assistant.enums import InputModality, SemanticType
from mesiri_contracts.assistant.normalized_message import NormalizedMessage, ReplyContext, SenderInfo
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.common.errors import ErrorCategory, ErrorCode, MesiriError
from mesiri_contracts.context.enums import (
    ContextAmbiguityField,
    InteractionKind,
    UserRole,
    WorkflowKind,
    WorkflowPhase,
)
from mesiri_contracts.context.ports import (
    ActiveWorkflowSnapshot,
    IdentityRecord,
    PendingInteractionSnapshot,
    ScopeRecord,
)


def _message(**kwargs) -> NormalizedMessage:
    base = dict(
        message_id="msg_1",
        correlation_id="cor_1",
        sender=SenderInfo(wa_id="919876543210", profile_name="Engineer"),
        timestamp=datetime(2026, 7, 6, 10, 0, tzinfo=UTC),
        modality=InputModality.TEXT,
        text="20 bags cement received",
    )
    base.update(kwargs)
    return NormalizedMessage(**base)


def _understanding(**kwargs) -> UnderstandingResult:
    base = dict(
        source_message_id="msg_1",
        correlation_id="cor_1",
        input_modality=InputModality.TEXT,
        semantic_type=SemanticType.MATERIAL_UPDATE,
    )
    base.update(kwargs)
    return UnderstandingResult(**base)


def _identity(**kwargs) -> IdentityRecord:
    base = dict(
        user_id="usr_1",
        organization_id="org_1",
        role=UserRole.SITE_ENGINEER,
        display_name="Site Engineer",
        whatsapp_wa_id="919876543210",
    )
    base.update(kwargs)
    return IdentityRecord(**base)


def _resolver(
    *,
    identity: FakeIdentityLookupPort | None = None,
    scope: FakeScopeLookupPort | None = None,
    workflow_state: FakeWorkflowStateReadPort | None = None,
) -> ContractContextResolver:
    return ContractContextResolver(
        identity=identity or FakeIdentityLookupPort(),
        scope=scope or FakeScopeLookupPort(),
        workflow_state=workflow_state or FakeWorkflowStateReadPort(),
    )


async def test_fully_resolved_context():
    identity = FakeIdentityLookupPort({_message().sender.wa_id: _identity()})
    scope = FakeScopeLookupPort(
        default_scopes={
            ("usr_1", "org_1"): ScopeRecord(
                project_id="prj_1",
                project_name="Tower A",
                site_id="site_1",
                site_name="Block 3",
            )
        }
    )
    resolver = _resolver(identity=identity, scope=scope)

    result = await resolver.resolve(_message(), _understanding())

    assert result.confidence is ConfidenceLevel.HIGH
    assert result.actor.user_id == "usr_1"
    assert result.actor.role is UserRole.SITE_ENGINEER
    assert result.scope.project_id == "prj_1"
    assert result.scope.site_id == "site_1"
    assert result.workflow is None
    assert result.interaction is None
    assert result.ambiguities == []


async def test_unknown_user():
    resolver = _resolver(identity=FakeIdentityLookupPort())

    result = await resolver.resolve(_message(), _understanding())

    assert result.actor.user_id is None
    assert result.confidence is ConfidenceLevel.LOW
    assert any(a.field is ContextAmbiguityField.USER for a in result.ambiguities)


async def test_unknown_project():
    identity = FakeIdentityLookupPort({_message().sender.wa_id: _identity()})
    scope = FakeScopeLookupPort(
        default_scopes={
            ("usr_1", "org_1"): ScopeRecord(site_id="site_1", site_name="Block 3"),
        }
    )
    resolver = _resolver(identity=identity, scope=scope)

    result = await resolver.resolve(_message(), _understanding())

    assert result.scope.project_id is None
    assert any(a.field is ContextAmbiguityField.PROJECT for a in result.ambiguities)
    assert result.confidence is ConfidenceLevel.LOW


async def test_unknown_site():
    identity = FakeIdentityLookupPort({_message().sender.wa_id: _identity()})
    scope = FakeScopeLookupPort(
        default_scopes={
            ("usr_1", "org_1"): ScopeRecord(project_id="prj_1", project_name="Tower A"),
        }
    )
    resolver = _resolver(identity=identity, scope=scope)

    result = await resolver.resolve(_message(), _understanding())

    assert result.scope.site_id is None
    assert any(a.field is ContextAmbiguityField.SITE for a in result.ambiguities)
    assert result.confidence is ConfidenceLevel.LOW


async def test_ambiguous_scope_no_record():
    identity = FakeIdentityLookupPort({_message().sender.wa_id: _identity()})
    scope = FakeScopeLookupPort(default_scopes={("usr_1", "org_1"): None})
    resolver = _resolver(identity=identity, scope=scope)

    result = await resolver.resolve(_message(), _understanding())

    assert result.scope.project_id is None
    assert any(a.field is ContextAmbiguityField.SCOPE for a in result.ambiguities)


async def test_active_workflow_found():
    identity = FakeIdentityLookupPort({_message().sender.wa_id: _identity()})
    scope = FakeScopeLookupPort(
        default_scopes={
            ("usr_1", "org_1"): ScopeRecord(
                project_id="prj_1", site_id="site_1",
            )
        }
    )
    workflow_state = FakeWorkflowStateReadPort(
        active_workflows={
            "usr_1": ActiveWorkflowSnapshot(
                workflow_instance_id="wf_1",
                workflow_kind=WorkflowKind.MATERIAL,
                phase=WorkflowPhase.AWAITING_CONFIRMATION,
            )
        }
    )
    resolver = _resolver(identity=identity, scope=scope, workflow_state=workflow_state)

    result = await resolver.resolve(_message(), _understanding())

    assert result.workflow is not None
    assert result.workflow.workflow_instance_id == "wf_1"
    assert result.workflow.workflow_kind is WorkflowKind.MATERIAL


async def test_pending_interaction_found():
    identity = FakeIdentityLookupPort({_message().sender.wa_id: _identity()})
    scope = FakeScopeLookupPort(
        default_scopes={("usr_1", "org_1"): ScopeRecord(project_id="prj_1", site_id="site_1")}
    )
    workflow_state = FakeWorkflowStateReadPort(
        pending_interactions={
            "usr_1": PendingInteractionSnapshot(
                interaction_id="int_1",
                kind=InteractionKind.CONFIRMATION,
                related_message_id="msg_prior",
            )
        }
    )
    resolver = _resolver(identity=identity, scope=scope, workflow_state=workflow_state)

    result = await resolver.resolve(_message(), _understanding())

    assert result.interaction is not None
    assert result.interaction.interaction_id == "int_1"
    assert result.interaction.kind is InteractionKind.CONFIRMATION


async def test_no_workflow_or_interaction():
    identity = FakeIdentityLookupPort({_message().sender.wa_id: _identity()})
    scope = FakeScopeLookupPort(
        default_scopes={("usr_1", "org_1"): ScopeRecord(project_id="prj_1", site_id="site_1")}
    )
    resolver = _resolver(identity=identity, scope=scope)

    result = await resolver.resolve(_message(), _understanding())

    assert result.workflow is None
    assert result.interaction is None


async def test_low_confidence_resolution():
    resolver = _resolver()

    result = await resolver.resolve(_message(), _understanding())

    assert result.confidence is ConfidenceLevel.LOW


async def test_multiple_ambiguities():
    resolver = _resolver()
    message = _message(correlation_id="cor_m2")
    understanding = _understanding(correlation_id="cor_m3")

    result = await resolver.resolve(message, understanding)

    fields = {a.field for a in result.ambiguities}
    assert ContextAmbiguityField.CORRELATION in fields
    assert ContextAmbiguityField.USER in fields
    assert result.confidence is ConfidenceLevel.LOW


async def test_port_failure_identity():
    err = MesiriError(
        error_code=ErrorCode.DEPENDENCY_FAILURE.value,
        category=ErrorCategory.DEPENDENCY,
        user_safe_message="identity unavailable",
    )
    identity = FakeIdentityLookupPort(fail_with=err)
    resolver = _resolver(identity=identity)

    result = await resolver.resolve(_message(), _understanding())

    assert "identity unavailable" in result.warnings
    assert any(a.field is ContextAmbiguityField.USER for a in result.ambiguities)


async def test_port_failure_scope():
    identity = FakeIdentityLookupPort({_message().sender.wa_id: _identity()})
    err = MesiriError(
        error_code=ErrorCode.DEPENDENCY_FAILURE.value,
        category=ErrorCategory.DEPENDENCY,
        user_safe_message="scope unavailable",
    )
    scope = FakeScopeLookupPort(fail_with=err)
    resolver = _resolver(identity=identity, scope=scope)

    result = await resolver.resolve(_message(), _understanding())

    assert "scope unavailable" in result.warnings
    assert any(a.field is ContextAmbiguityField.SCOPE for a in result.ambiguities)


async def test_port_failure_workflow_state():
    identity = FakeIdentityLookupPort({_message().sender.wa_id: _identity()})
    scope = FakeScopeLookupPort(
        default_scopes={("usr_1", "org_1"): ScopeRecord(project_id="prj_1", site_id="site_1")}
    )
    err = MesiriError(
        error_code=ErrorCode.DEPENDENCY_FAILURE.value,
        category=ErrorCategory.DEPENDENCY,
        user_safe_message="workflow state unavailable",
    )
    workflow_state = FakeWorkflowStateReadPort(fail_with=err)
    resolver = _resolver(identity=identity, scope=scope, workflow_state=workflow_state)

    result = await resolver.resolve(_message(), _understanding())

    assert "workflow state unavailable" in result.warnings
    assert any(a.field is ContextAmbiguityField.WORKFLOW for a in result.ambiguities)
    assert result.confidence is ConfidenceLevel.MEDIUM


async def test_missing_optional_values():
    identity = FakeIdentityLookupPort(
        {
            _message().sender.wa_id: _identity(
                organization_id=None,
                display_name=None,
            )
        }
    )
    resolver = _resolver(identity=identity)

    result = await resolver.resolve(_message(), _understanding())

    assert result.reply.replied_to_message_id is None
    assert result.workflow is None
    assert result.interaction is None
    assert result.actor.display_name == "Engineer"
    assert any(a.field is ContextAmbiguityField.ORGANIZATION for a in result.ambiguities)


async def test_reply_scope_precedence():
    identity = FakeIdentityLookupPort({_message().sender.wa_id: _identity()})
    scope = FakeScopeLookupPort(
        default_scopes={
            ("usr_1", "org_1"): ScopeRecord(project_id="prj_default", site_id="site_default"),
        },
        reply_scopes={
            "msg_parent": ScopeRecord(project_id="prj_reply", site_id="site_reply"),
        },
    )
    resolver = _resolver(identity=identity, scope=scope)
    message = _message(
        reply_context=ReplyContext(replied_to_message_id="msg_parent"),
    )

    result = await resolver.resolve(message, _understanding())

    assert result.scope.project_id == "prj_reply"
    assert result.scope.site_id == "site_reply"
    assert result.reply.binds_to_prior_journey is True
    assert any("reply binding" in w for w in result.warnings)


async def test_resolved_context_is_schema_valid():
    identity = FakeIdentityLookupPort({_message().sender.wa_id: _identity(role=UserRole.OWNER)})
    scope = FakeScopeLookupPort(
        default_scopes={("usr_1", "org_1"): ScopeRecord(project_id="prj_1", site_id="site_1")}
    )
    resolver = _resolver(identity=identity, scope=scope)

    result = await resolver.resolve(_message(), _understanding())

    from mesiri_contracts.context import ResolvedContext

    assert isinstance(result, ResolvedContext)
    ResolvedContext.model_validate(result.model_dump())
