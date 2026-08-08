"""ResolvedContext v2 contract validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mesiri_contracts.assistant.context_enums import ContextConfidence, ContextSource
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"


def test_dual_namespace_round_trip():
    ctx = ResolvedContextV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        context_organization_id="ctx_org_" + ORG,
        context_user_id="ctx_user_" + USR,
        context_project_id="ctx_proj_" + PRJ,
        context_site_id="ctx_site_" + SITE,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=SITE,
        permissions=["expense.create"],
        context_source=ContextSource.USER_DEFAULT,
        context_confidence=ContextConfidence.HIGH,
    )
    assert ctx.version == "v2"
    assert ctx.organization_id == ORG.lower()
    assert ctx.context_organization_id == "ctx_org_" + ORG


def test_project_id_requires_context_project_id():
    with pytest.raises(ValidationError):
        ResolvedContextV2(
            correlation_id="cor_1",
            source_message_id="msg_1",
            context_organization_id="org_a",
            context_user_id="usr_a",
            organization_id=ORG,
            user_id=USR,
            project_id=PRJ,
        )


def test_invalid_uuid_rejected():
    with pytest.raises(ValidationError):
        ResolvedContextV2(
            correlation_id="cor_1",
            source_message_id="msg_1",
            context_organization_id="org_a",
            context_user_id="usr_a",
            organization_id="not-a-uuid",
            user_id=USR,
        )
