"""M6.5 E2E — v2 identity propagates from resolver through workflow save."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from canonicalization import build_canonical_event
from context.active_context import RedisActiveContextStore
from context.identity_bridge import (
    PostgresIdentityBridgeRepository,
    context_organization_id,
    context_user_id,
)
from context.identity_projection import IdentityProjectionService
from context.postgres_repositories import (
    PostgresContextPreferenceRepository,
    PostgresExternalIdentityRepository,
    PostgresMembershipRepository,
    PostgresProjectRepository,
    PostgresRolePermissionRepository,
    PostgresSiteRepository,
)
from context.reply_context import NullReplyContextProvider
from context.resolver import ContextDependencies, ContextResolver
from context.workflow_context import NullWorkflowContextProvider
from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.redis.client import RedisClient
from mesiri_contracts.assistant.candidates import MaterialUpdateCandidate
from mesiri_contracts.assistant.enums import InputModality, SemanticType
from mesiri_contracts.assistant.normalized_message import NormalizedMessage, SenderInfo
from mesiri_contracts.assistant.planner_decision import PlannerDecisionType, WorkflowKey
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from planner import Planner
from workflows.fakes import FakeCompiledGraph, FakeWorkflowInstanceRepository, FakeWorkflowRegistry
from workflows.runtime import WorkflowRunStatus, WorkflowRuntime

pytestmark = pytest.mark.integration

WA = "+919888877766"


@pytest.fixture
async def identity_world():
    from sqlalchemy.ext.asyncio import create_async_engine

    settings = Settings()
    engine = create_async_engine(settings.postgres.dsn())
    sync_engine = IdentityProjectionService()._engine

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    from sqlalchemy import text

    with sync_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO organizations (id, name, status) VALUES (:id, :name, 'Active')"
            ),
            {"id": org_id, "name": "E2E Org"},
        )
        conn.execute(
            text(
                "INSERT INTO users (id, full_name, organization_id, whatsapp_number, status) "
                "VALUES (:id, :name, :org, :wa, 'active')"
            ),
            {"id": user_id, "name": "E2E User", "org": org_id, "wa": WA},
        )

    service = IdentityProjectionService(engine=sync_engine)
    service.project_one("organization", org_id)
    service.project_one("user", user_id)

    redis = RedisClient(settings.redis)
    await redis.connect()
    store = RedisActiveContextStore(redis)

    deps = ContextDependencies(
        identities=PostgresExternalIdentityRepository(engine),
        memberships=PostgresMembershipRepository(engine),
        roles=PostgresRolePermissionRepository(engine),
        projects=PostgresProjectRepository(engine),
        sites=PostgresSiteRepository(engine),
        preferences=PostgresContextPreferenceRepository(engine),
        active_context=store,
        reply_context=NullReplyContextProvider(),
        workflow_context=NullWorkflowContextProvider(),
        bridge=PostgresIdentityBridgeRepository(engine),
    )

    yield {
        "engine": engine,
        "sync_engine": sync_engine,
        "deps": deps,
        "org_id": org_id,
        "user_id": user_id,
    }

    ctx_org = context_organization_id(org_id)
    ctx_user = context_user_id(user_id)
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM external_identities WHERE user_id = :u"), {"u": ctx_user})
        conn.execute(
            text("DELETE FROM organization_memberships WHERE organization_id = :o"),
            {"o": ctx_org},
        )
        conn.execute(text("DELETE FROM context_users WHERE id = :u"), {"u": ctx_user})
        conn.execute(text("DELETE FROM context_organizations WHERE id = :o"), {"o": ctx_org})
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        conn.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})
    await redis.disconnect()
    await engine.dispose()


async def test_v2_identity_propagates_to_workflow_state(identity_world) -> None:
    org_id = identity_world["org_id"]
    user_id = identity_world["user_id"]
    deps = identity_world["deps"]

    msg = NormalizedMessage(
        message_id="msg_e2e",
        correlation_id="cor_e2e",
        channel="whatsapp",
        sender=SenderInfo(wa_id=WA),
        timestamp=datetime.now(UTC),
        modality=InputModality.TEXT,
        text="received 20 bags cement",
    )
    understanding = UnderstandingResult(
        source_message_id="msg_e2e",
        correlation_id="cor_e2e",
        input_modality=InputModality.TEXT,
        semantic_type=SemanticType.MATERIAL_UPDATE,
        candidates=[
            MaterialUpdateCandidate(
                fields={"material_name": "cement", "quantity": 20, "unit": "bags", "direction": "received"}
            )
        ],
    )

    resolved = (await ContextResolver(deps).resolve(msg, understanding)).unwrap()
    assert resolved.version == "v2"
    assert resolved.organization_id == str(org_id)
    assert resolved.context_organization_id == context_organization_id(org_id)
    assert resolved.user_id == str(user_id)

    event = build_canonical_event(understanding, resolved)
    assert event.version == "v2"
    assert event.organization_id == str(org_id)

    decision = Planner().decide(event)
    assert decision.version == "v2"
    assert decision.decision_type is PlannerDecisionType.START_WORKFLOW
    assert decision.workflow_key is WorkflowKey.MATERIAL_RECEIPT

    from mesiri_contracts.assistant.draft_action import DraftActionType
    from mesiri_contracts.assistant.v2.draft_action import DraftActionV2

    draft = DraftActionV2(
        draft_id="draft_e2e",
        correlation_id="cor_e2e",
        workflow_instance_id="wf_e2e",
        action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
        organization_id=str(org_id),
        user_id=str(user_id),
        fields=event.fields,
    )
    graph = FakeCompiledGraph({"draft_action": draft, "pending_prompt": "Confirm?"})
    repo = FakeWorkflowInstanceRepository()
    runtime = WorkflowRuntime(
        registry=FakeWorkflowRegistry({WorkflowKey.MATERIAL_RECEIPT: graph}),
        repo=repo,
    )
    result = await runtime.start(decision, event)
    assert result.status is WorkflowRunStatus.STARTED
    saved = repo.saved[0]
    assert saved.version == "v2"
    assert saved.organization_id == str(org_id)
    assert saved.user_id == str(user_id)
