"""M4 Context Foundation — the 20 required gate scenarios.

Each scenario is expressed Given/When/Then in its docstring and asserts the
ResolvedContext, context source, error result, and (where relevant) Redis
effects. All run against deterministic fakes — no live Postgres/Redis, no AI
providers (UnderstandingResult is a fixture). Tenant isolation, precedence,
ambiguity, active-context persistence, and correlation are all covered.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from context import seed
from context.fakes import FakeActiveContextStore
from context.identity_bridge import deterministic_canonical_uuid as canon
from context.resolver import ContextResolver
from context.service import ContextSwitchService
from mesiri_contracts.assistant.candidates import EquipmentUsageCandidate
from mesiri_contracts.assistant.context_enums import ContextConfidence, ContextSource
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import (
    NormalizedMessage,
    ReplyContext,
    SenderInfo,
)
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.common.errors import ErrorCode

pytestmark = pytest.mark.scenario


def _msg(wa_id, *, correlation_id="cor_s", message_id="msg_s", reply_to=None):
    return NormalizedMessage(
        message_id=message_id,
        correlation_id=correlation_id,
        channel="whatsapp",
        sender=SenderInfo(wa_id=wa_id),
        timestamp=datetime.now(UTC),
        modality=InputModality.TEXT,
        text="msg",
        reply_context=ReplyContext(replied_to_message_id=reply_to) if reply_to else None,
    )


def _und(fields=None, *, correlation_id="cor_s", message_id="msg_s"):
    cands = [EquipmentUsageCandidate(fields=fields)] if fields else []
    return UnderstandingResult(
        source_message_id=message_id,
        correlation_id=correlation_id,
        input_modality=InputModality.TEXT,
        candidates=cands,
    )


# --------------------------------------------------------------------------- #


async def test_scenario_m4_001_unknown_whatsapp_user():
    """Given an unregistered wa_id, When resolved, Then UNKNOWN_EXTERNAL_IDENTITY."""
    r = ContextResolver(seed.build_dependencies())
    res = await r.resolve(_msg(seed.WA_UNKNOWN), _und())
    assert res.is_err and res.error.error_code == ErrorCode.UNKNOWN_EXTERNAL_IDENTITY.value


async def test_scenario_m4_002_engineer_single_project():
    """Given a single-project engineer, Then project auto-resolves via USER_DEFAULT."""
    r = ContextResolver(seed.build_dependencies())
    ctx = (await r.resolve(_msg(seed.WA_ENGINEER), _und())).unwrap()
    assert ctx.context_project_id == seed.PROJ_ALPHA
    assert ctx.project_id == canon(seed.PROJ_ALPHA)
    assert ctx.context_source == ContextSource.USER_DEFAULT


async def test_scenario_m4_003_engineer_multiple_projects_unresolved_without_signal():
    """Given a multi-project user with no default/active/explicit, Then UNRESOLVED."""
    world = seed.build_world()
    world.preferences = [p for p in world.preferences if p.user_id != seed.USER_DIRECTOR]
    r = ContextResolver(seed.build_dependencies(world))
    ctx = (await r.resolve(_msg(seed.WA_DIRECTOR), _und())).unwrap()
    assert ctx.project_id is None
    assert ctx.context_source == ContextSource.UNRESOLVED


async def test_scenario_m4_004_director_multiple_projects_default():
    """Given a director with a default assignment, Then default project resolves."""
    r = ContextResolver(seed.build_dependencies())
    ctx = (await r.resolve(_msg(seed.WA_DIRECTOR), _und())).unwrap()
    assert ctx.context_project_id == seed.PROJ_ALPHA
    assert ctx.project_id == canon(seed.PROJ_ALPHA)
    assert ctx.context_source == ContextSource.USER_DEFAULT


async def test_scenario_m4_005_default_project_resolution():
    """Given the ABC director default = Airport, Then it resolves with MEDIUM confidence."""
    r = ContextResolver(seed.build_dependencies())
    ctx = (await r.resolve(_msg(seed.WA_ABC_DIRECTOR), _und())).unwrap()
    assert ctx.context_project_id == seed.PROJ_AIRPORT
    assert ctx.project_id == canon(seed.PROJ_AIRPORT)
    assert ctx.context_confidence == ContextConfidence.MEDIUM


async def test_scenario_m4_006_explicit_project_resolution():
    """Given "Project Beta" named, Then MESSAGE_EXPLICIT / HIGH confidence."""
    r = ContextResolver(seed.build_dependencies())
    ctx = (await r.resolve(_msg(seed.WA_DIRECTOR), _und({"project_name": "Project Beta"}))).unwrap()
    assert ctx.context_project_id == seed.PROJ_BETA
    assert ctx.project_id == canon(seed.PROJ_BETA)
    assert ctx.context_source == ContextSource.MESSAGE_EXPLICIT
    assert ctx.context_confidence == ContextConfidence.HIGH


async def test_scenario_m4_007_explicit_site_resolution():
    """Given "Block A" named by the ABC director, Then site + inferred project resolve."""
    r = ContextResolver(seed.build_dependencies())
    ctx = (await r.resolve(_msg(seed.WA_ABC_DIRECTOR), _und({"site_name": "Block A"}))).unwrap()
    assert ctx.context_site_id == seed.SITE_BLOCK_A
    assert ctx.site_id == canon(seed.SITE_BLOCK_A)
    assert ctx.context_project_id == seed.PROJ_MARINA
    assert ctx.project_id == canon(seed.PROJ_MARINA)


async def test_scenario_m4_008_unauthorized_project():
    """Given an engineer naming a project id in-org but unassigned, Then ACCESS_DENIED."""
    r = ContextResolver(seed.build_dependencies())
    res = await r.resolve(_msg(seed.WA_ENGINEER), _und({"project_id": seed.PROJ_BETA}))
    assert res.is_err and res.error.error_code == ErrorCode.PROJECT_ACCESS_DENIED.value


async def test_scenario_m4_009_ambiguous_project():
    """Given two authorized projects with the same name, Then AMBIGUOUS_PROJECT."""
    world = seed.build_world()
    world.projects.append(world.projects[0].__class__("proj_dupe", seed.ORG_A, "Project Beta"))
    world.project_access[seed.USER_DIRECTOR].add("proj_dupe")
    r = ContextResolver(seed.build_dependencies(world))
    res = await r.resolve(_msg(seed.WA_DIRECTOR), _und({"project_name": "Project Beta"}))
    assert res.is_err and res.error.error_code == ErrorCode.AMBIGUOUS_PROJECT.value


async def test_scenario_m4_010_active_project_switch():
    """Given a switch to Marina Tower, Then Redis active context is set + authorized."""
    deps = seed.build_dependencies()
    svc = ContextSwitchService(
        projects=deps.projects, sites=deps.sites, active_context=deps.active_context
    )
    res = await svc.select_active_context(
        organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR, project_id=seed.PROJ_MARINA
    )
    assert res.is_ok
    stored = await deps.active_context.get_active_context(
        organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR
    )
    assert stored.project_id == seed.PROJ_MARINA


async def test_scenario_m4_011_next_message_uses_active_context():
    """Given an active Marina context, When a later message arrives, Then ACTIVE_CONTEXT wins."""
    active = FakeActiveContextStore()
    deps = seed.build_dependencies(active_store=active)
    svc = ContextSwitchService(projects=deps.projects, sites=deps.sites, active_context=active)
    await svc.select_active_context(
        organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR, project_id=seed.PROJ_MARINA
    )
    r = ContextResolver(deps)
    ctx = (
        await r.resolve(
            _msg(seed.WA_ABC_DIRECTOR), _und({"equipment_name": "JCB", "duration_hours": 4})
        )
    ).unwrap()
    assert ctx.context_project_id == seed.PROJ_MARINA
    assert ctx.project_id == canon(seed.PROJ_MARINA)
    assert ctx.context_source == ContextSource.ACTIVE_CONTEXT


async def test_scenario_m4_012_reply_context_overrides_active_context():
    active = FakeActiveContextStore()
    await active.set_active_context(
        organization_id=seed.ABC_ORG,
        user_id=seed.ABC_DIRECTOR,
        project_id=seed.PROJ_MARINA,
        site_id=None,
        ttl_seconds=3600,
    )
    r = ContextResolver(
        seed.build_dependencies(
            active_store=active, reply_mapping={"orig": (seed.PROJ_AIRPORT, None)}
        )
    )
    ctx = (await r.resolve(_msg(seed.WA_ABC_DIRECTOR, reply_to="orig"), _und())).unwrap()
    assert ctx.context_project_id == seed.PROJ_AIRPORT
    assert ctx.project_id == canon(seed.PROJ_AIRPORT)
    assert ctx.context_source == ContextSource.REPLY_CONTEXT


async def test_scenario_m4_013_workflow_context_overrides_active_context():
    active = FakeActiveContextStore()
    await active.set_active_context(
        organization_id=seed.ABC_ORG,
        user_id=seed.ABC_DIRECTOR,
        project_id=seed.PROJ_MARINA,
        site_id=None,
        ttl_seconds=3600,
    )
    r = ContextResolver(
        seed.build_dependencies(
            active_store=active,
            workflow_mapping={(seed.ABC_ORG, seed.ABC_DIRECTOR): (seed.PROJ_AIRPORT, None)},
        )
    )
    ctx = (await r.resolve(_msg(seed.WA_ABC_DIRECTOR), _und())).unwrap()
    assert ctx.context_project_id == seed.PROJ_AIRPORT
    assert ctx.project_id == canon(seed.PROJ_AIRPORT)
    assert ctx.context_source == ContextSource.WORKFLOW_CONTEXT


async def test_scenario_m4_014_active_context_survives_app_restart():
    """Given active context in Redis, When the app 'restarts' (new store on same
    backend), Then the selection is still readable."""
    from context.active_context import RedisActiveContextStore
    from mesiri.infrastructure.redis.client import FakeRedis

    redis = FakeRedis()
    await redis.connect()
    store1 = RedisActiveContextStore(redis)
    await store1.set_active_context(
        organization_id=seed.ABC_ORG,
        user_id=seed.ABC_DIRECTOR,
        project_id=seed.PROJ_MARINA,
        site_id=None,
        ttl_seconds=3600,
    )
    # Simulate restart: brand-new store instance over the same Redis backend.
    store2 = RedisActiveContextStore(redis)
    got = await store2.get_active_context(organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR)
    assert got is not None and got.project_id == seed.PROJ_MARINA


async def test_scenario_m4_015_active_context_expires():
    clock = {"now": datetime(2026, 1, 1, tzinfo=UTC)}
    active = FakeActiveContextStore(clock=lambda: clock["now"])
    await active.set_active_context(
        organization_id=seed.ABC_ORG,
        user_id=seed.ABC_DIRECTOR,
        project_id=seed.PROJ_MARINA,
        site_id=None,
        ttl_seconds=60,
    )
    clock["now"] += timedelta(seconds=61)
    r = ContextResolver(seed.build_dependencies(active_store=active))
    ctx = (await r.resolve(_msg(seed.WA_ABC_DIRECTOR), _und())).unwrap()
    # Expired active context ignored -> default (Airport) resolves.
    assert ctx.context_project_id == seed.PROJ_AIRPORT
    assert ctx.project_id == canon(seed.PROJ_AIRPORT)
    assert ctx.context_source == ContextSource.USER_DEFAULT


async def test_scenario_m4_016_cross_organization_access_attempt():
    """Given an Org B user naming Org A's project id, Then it never resolves (isolation)."""
    r = ContextResolver(seed.build_dependencies())
    res = await r.resolve(_msg(seed.WA_ORGB), _und({"project_id": seed.PROJ_ALPHA}))
    assert res.is_err and res.error.error_code == ErrorCode.PROJECT_NOT_FOUND.value


async def test_scenario_m4_017_disabled_membership():
    r = ContextResolver(seed.build_dependencies())
    res = await r.resolve(_msg(seed.WA_DISABLED), _und())
    assert res.is_err and res.error.error_code == ErrorCode.MEMBERSHIP_NOT_FOUND.value


async def test_scenario_m4_018_project_site_mismatch():
    r = ContextResolver(seed.build_dependencies())
    res = await r.resolve(
        _msg(seed.WA_DIRECTOR),
        _und({"project_id": seed.PROJ_ALPHA, "site_id": seed.SITE_B1}),
    )
    assert res.is_err and res.error.error_code == ErrorCode.PROJECT_SITE_MISMATCH.value


async def test_scenario_m4_019_context_correction():
    """Given active=Marina, When the user explicitly corrects to Airport, Then explicit wins."""
    active = FakeActiveContextStore()
    await active.set_active_context(
        organization_id=seed.ABC_ORG,
        user_id=seed.ABC_DIRECTOR,
        project_id=seed.PROJ_MARINA,
        site_id=None,
        ttl_seconds=3600,
    )
    r = ContextResolver(seed.build_dependencies(active_store=active))
    ctx = (
        await r.resolve(_msg(seed.WA_ABC_DIRECTOR), _und({"project_name": "Airport Expansion"}))
    ).unwrap()
    assert ctx.context_project_id == seed.PROJ_AIRPORT
    assert ctx.project_id == canon(seed.PROJ_AIRPORT)
    assert ctx.context_source == ContextSource.MESSAGE_EXPLICIT


async def test_scenario_m4_020_correlation_preserved():
    r = ContextResolver(seed.build_dependencies())
    ctx = (
        await r.resolve(
            _msg(seed.WA_ENGINEER, correlation_id="cor_journey", message_id="msg_journey"),
            _und(correlation_id="cor_journey", message_id="msg_journey"),
        )
    ).unwrap()
    assert ctx.correlation_id == "cor_journey"
    assert ctx.source_message_id == "msg_journey"
    assert ctx.causation_id == "msg_journey"
