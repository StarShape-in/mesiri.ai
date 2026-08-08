"""Resolver bridge lookup — missing bridge must fail with CANONICAL_IDENTITY_NOT_MAPPED."""

from __future__ import annotations

from datetime import UTC, datetime

from context import seed
from context.identity_bridge import FakeIdentityBridgeRepository
from context.resolver import ContextResolver
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage, SenderInfo
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.common.errors import ErrorCode


def _msg(wa_id: str) -> NormalizedMessage:
    return NormalizedMessage(
        message_id="msg_bridge",
        correlation_id="cor_bridge",
        channel="whatsapp",
        sender=SenderInfo(wa_id=wa_id),
        timestamp=datetime.now(UTC),
        modality=InputModality.TEXT,
        text="hi",
    )


def _understanding() -> UnderstandingResult:
    return UnderstandingResult(
        source_message_id="msg_bridge",
        correlation_id="cor_bridge",
        input_modality=InputModality.TEXT,
        candidates=[],
    )


async def test_missing_bridge_returns_canonical_identity_not_mapped():
    class _NullBridge(FakeIdentityBridgeRepository):
        async def canonical_organization_id(self, context_organization_id: str) -> str | None:
            return None

    base = seed.build_dependencies()
    from context.resolver import ContextDependencies

    deps = ContextDependencies(
        identities=base.identities,
        memberships=base.memberships,
        roles=base.roles,
        projects=base.projects,
        sites=base.sites,
        preferences=base.preferences,
        active_context=base.active_context,
        reply_context=base.reply_context,
        workflow_context=base.workflow_context,
        bridge=_NullBridge(),
    )
    resolver = ContextResolver(deps)
    result = await resolver.resolve(_msg(seed.WA_ENGINEER), _understanding())
    assert result.is_err
    assert result.error.error_code == ErrorCode.CANONICAL_IDENTITY_NOT_MAPPED.value


async def test_bridge_resolves_v2_canonical_scope():
    resolver = ContextResolver(seed.build_dependencies())
    result = await resolver.resolve(_msg(seed.WA_ENGINEER), _understanding())
    assert result.is_ok
    ctx = result.unwrap()
    assert ctx.version == "v2"
    assert ctx.context_organization_id == seed.ORG_A
    assert ctx.organization_id != seed.ORG_A
