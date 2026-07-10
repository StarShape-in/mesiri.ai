"""M4 Context Foundation — unit tests (fakes only; no live Postgres/Redis)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from context import seed
from context.active_context import RedisActiveContextStore
from context.fakes import FakeActiveContextStore
from context.identity_bridge import deterministic_canonical_uuid as canon
from context.resolver import ContextResolver
from context.service import ContextSwitchService
from mesiri_contracts.assistant.candidates import ExpenseCandidate
from mesiri_contracts.assistant.context_enums import ContextConfidence, ContextSource
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import (
    NormalizedMessage,
    ReplyContext,
    SenderInfo,
)
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.common.errors import ErrorCode

# -- Builders ----------------------------------------------------------------


def msg(
    wa_id: str,
    *,
    correlation_id: str = "cor_test",
    message_id: str = "msg_1",
    reply_to: str | None = None,
) -> NormalizedMessage:
    return NormalizedMessage(
        message_id=message_id,
        correlation_id=correlation_id,
        channel="whatsapp",
        sender=SenderInfo(wa_id=wa_id),
        timestamp=datetime.now(UTC),
        modality=InputModality.TEXT,
        text="hi",
        reply_context=ReplyContext(replied_to_message_id=reply_to) if reply_to else None,
    )


def understanding(
    *,
    fields: dict | None = None,
    correlation_id: str = "cor_test",
    message_id: str = "msg_1",
) -> UnderstandingResult:
    candidates = [ExpenseCandidate(fields=fields)] if fields else []
    return UnderstandingResult(
        source_message_id=message_id,
        correlation_id=correlation_id,
        input_modality=InputModality.TEXT,
        candidates=candidates,
    )


def resolver(**kwargs) -> ContextResolver:
    return ContextResolver(seed.build_dependencies(**kwargs))


async def resolve(wa_id: str, *, fields: dict | None = None, **dep_kwargs):
    r = resolver(**dep_kwargs)
    return await r.resolve(msg(wa_id), understanding(fields=fields))


# -- Identity resolution -----------------------------------------------------


async def test_unknown_identity_rejected():
    res = await resolve(seed.WA_UNKNOWN)
    assert res.is_err
    assert res.error.error_code == ErrorCode.UNKNOWN_EXTERNAL_IDENTITY.value


async def test_disabled_membership_rejected():
    res = await resolve(seed.WA_DISABLED)
    assert res.is_err
    # No active membership remains -> membership_not_found.
    assert res.error.error_code == ErrorCode.MEMBERSHIP_NOT_FOUND.value


async def test_disabled_user_rejected():
    world = seed.build_world()
    world.users = [
        (u.__class__(u.user_id, is_active=False) if u.user_id == seed.USER_ENGINEER else u)
        for u in world.users
    ]
    r = ContextResolver(seed.build_dependencies(world))
    res = await r.resolve(msg(seed.WA_ENGINEER), understanding())
    assert res.is_err
    assert res.error.error_code == ErrorCode.USER_DISABLED.value


async def test_identity_resolves_authoritative_org_and_permissions():
    res = await resolve(seed.WA_ENGINEER)
    assert res.is_ok
    ctx = res.unwrap()
    assert ctx.context_organization_id == seed.ORG_A
    assert ctx.organization_id == canon(seed.ORG_A)
    assert ctx.context_user_id == seed.USER_ENGINEER
    assert ctx.user_id == canon(seed.USER_ENGINEER)
    assert ctx.membership_id == "mem_eng"
    assert "expense.create" in ctx.permissions
    assert seed.ROLE_ENGINEER in ctx.role_ids


# -- Project resolution ------------------------------------------------------


async def test_engineer_single_project_auto_resolves():
    res = await resolve(seed.WA_ENGINEER)
    ctx = res.unwrap()
    assert ctx.context_project_id == seed.PROJ_ALPHA
    assert ctx.context_source == ContextSource.USER_DEFAULT


async def test_director_multiple_projects_uses_default():
    res = await resolve(seed.WA_DIRECTOR)
    ctx = res.unwrap()
    assert ctx.context_project_id == seed.PROJ_ALPHA  # default assignment
    assert ctx.context_source == ContextSource.USER_DEFAULT


async def test_explicit_project_name_resolves_high_confidence():
    r = resolver()
    res = await r.resolve(
        msg(seed.WA_DIRECTOR), understanding(fields={"project_name": "Project Beta"})
    )
    ctx = res.unwrap()
    assert ctx.context_project_id == seed.PROJ_BETA
    assert ctx.context_source == ContextSource.MESSAGE_EXPLICIT
    assert ctx.context_confidence == ContextConfidence.HIGH


async def test_explicit_project_id_resolves_very_high_confidence():
    r = resolver()
    res = await r.resolve(
        msg(seed.WA_DIRECTOR), understanding(fields={"project_id": seed.PROJ_BETA})
    )
    ctx = res.unwrap()
    assert ctx.context_project_id == seed.PROJ_BETA
    assert ctx.context_confidence == ContextConfidence.VERY_HIGH


async def test_explicit_site_resolves_and_infers_project():
    r = resolver()
    res = await r.resolve(msg(seed.WA_ENGINEER), understanding(fields={"site_name": "Site A2"}))
    ctx = res.unwrap()
    assert ctx.context_site_id == seed.SITE_A2
    assert ctx.context_project_id == seed.PROJ_ALPHA


async def test_unauthorized_project_denied():
    # Engineer names Project Beta by id (exists in org, not assigned).
    r = resolver()
    res = await r.resolve(
        msg(seed.WA_ENGINEER), understanding(fields={"project_id": seed.PROJ_BETA})
    )
    assert res.is_err
    assert res.error.error_code == ErrorCode.PROJECT_ACCESS_DENIED.value


async def test_unknown_project_name_not_found():
    r = resolver()
    res = await r.resolve(
        msg(seed.WA_ENGINEER), understanding(fields={"project_name": "Nonexistent"})
    )
    assert res.is_err
    assert res.error.error_code == ErrorCode.PROJECT_NOT_FOUND.value


async def test_project_site_mismatch():
    r = resolver()
    res = await r.resolve(
        msg(seed.WA_DIRECTOR),
        understanding(fields={"project_id": seed.PROJ_ALPHA, "site_id": seed.SITE_B1}),
    )
    assert res.is_err
    assert res.error.error_code == ErrorCode.PROJECT_SITE_MISMATCH.value


# -- Ambiguity ---------------------------------------------------------------


async def test_ambiguous_project_across_authorized_matches():
    # Give the director two authorized projects both named "Marina Tower".
    world = seed.build_world()
    world.projects.append(world.projects[0].__class__("proj_dupe", seed.ORG_A, "Project Beta"))
    world.project_access[seed.USER_DIRECTOR].add("proj_dupe")
    r = ContextResolver(seed.build_dependencies(world))
    res = await r.resolve(
        msg(seed.WA_DIRECTOR), understanding(fields={"project_name": "Project Beta"})
    )
    assert res.is_err
    assert res.error.error_code == ErrorCode.AMBIGUOUS_PROJECT.value
    assert len(res.error.details["project_ids"]) == 2


# -- Cross-organization isolation --------------------------------------------


async def test_cross_org_same_name_isolated():
    # Org B user asks for "Project Alpha" -> resolves ORG B project, never ORG A.
    r = resolver()
    res = await r.resolve(
        msg(seed.WA_ORGB), understanding(fields={"project_name": "Project Alpha"})
    )
    ctx = res.unwrap()
    assert ctx.context_organization_id == seed.ORG_B
    assert ctx.organization_id == canon(seed.ORG_B)
    assert ctx.context_project_id == seed.PROJ_ALPHA_B


async def test_cross_org_project_id_denied_as_not_found():
    # Org B user names ORG A's project id -> must NOT resolve (tenant isolation).
    r = resolver()
    res = await r.resolve(msg(seed.WA_ORGB), understanding(fields={"project_id": seed.PROJ_ALPHA}))
    assert res.is_err
    assert res.error.error_code == ErrorCode.PROJECT_NOT_FOUND.value


# -- Precedence --------------------------------------------------------------


async def test_active_context_precedence_over_default():
    active = FakeActiveContextStore()
    await active.set_active_context(
        organization_id=seed.ABC_ORG,
        user_id=seed.ABC_DIRECTOR,
        project_id=seed.PROJ_MARINA,
        site_id=None,
        ttl_seconds=3600,
    )
    r = ContextResolver(seed.build_dependencies(active_store=active))
    res = await r.resolve(msg(seed.WA_ABC_DIRECTOR), understanding())
    ctx = res.unwrap()
    assert ctx.context_project_id == seed.PROJ_MARINA  # active beats default (Airport)
    assert ctx.context_source == ContextSource.ACTIVE_CONTEXT


async def test_explicit_precedence_over_active():
    active = FakeActiveContextStore()
    await active.set_active_context(
        organization_id=seed.ABC_ORG,
        user_id=seed.ABC_DIRECTOR,
        project_id=seed.PROJ_MARINA,
        site_id=None,
        ttl_seconds=3600,
    )
    r = ContextResolver(seed.build_dependencies(active_store=active))
    res = await r.resolve(
        msg(seed.WA_ABC_DIRECTOR), understanding(fields={"project_name": "Airport Expansion"})
    )
    ctx = res.unwrap()
    assert ctx.context_project_id == seed.PROJ_AIRPORT
    assert ctx.context_source == ContextSource.MESSAGE_EXPLICIT


async def test_reply_context_precedence_over_active():
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
            reply_mapping={"orig_msg": (seed.PROJ_AIRPORT, None)},
        )
    )
    res = await r.resolve(msg(seed.WA_ABC_DIRECTOR, reply_to="orig_msg"), understanding())
    ctx = res.unwrap()
    assert ctx.context_project_id == seed.PROJ_AIRPORT
    assert ctx.context_source == ContextSource.REPLY_CONTEXT


async def test_workflow_context_precedence_over_active():
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
    res = await r.resolve(msg(seed.WA_ABC_DIRECTOR), understanding())
    ctx = res.unwrap()
    assert ctx.context_project_id == seed.PROJ_AIRPORT
    assert ctx.context_source == ContextSource.WORKFLOW_CONTEXT


# -- Stale / expiry ----------------------------------------------------------


async def test_stale_active_context_rejected_falls_to_default():
    active = FakeActiveContextStore()
    # Store a project the director is NOT authorized for (Org A's Alpha).
    await active.set_active_context(
        organization_id=seed.ABC_ORG,
        user_id=seed.ABC_DIRECTOR,
        project_id=seed.PROJ_ALPHA,
        site_id=None,
        ttl_seconds=3600,
    )
    r = ContextResolver(seed.build_dependencies(active_store=active))
    res = await r.resolve(msg(seed.WA_ABC_DIRECTOR), understanding())
    ctx = res.unwrap()
    # Stale active dropped -> default (Airport) wins.
    assert ctx.context_project_id == seed.PROJ_AIRPORT
    assert ctx.context_source == ContextSource.USER_DEFAULT


async def test_active_context_expiry_via_clock():
    clock_time = {"now": datetime(2026, 1, 1, tzinfo=UTC)}
    active = FakeActiveContextStore(clock=lambda: clock_time["now"])
    await active.set_active_context(
        organization_id=seed.ABC_ORG,
        user_id=seed.ABC_DIRECTOR,
        project_id=seed.PROJ_MARINA,
        site_id=None,
        ttl_seconds=60,
    )
    got = await active.get_active_context(organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR)
    assert got is not None
    clock_time["now"] += timedelta(seconds=61)
    got = await active.get_active_context(organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR)
    assert got is None


# -- Active context switch service -------------------------------------------


async def test_switch_service_authorizes_and_persists():
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


async def test_switch_service_rejects_unauthorized_project():
    deps = seed.build_dependencies()
    svc = ContextSwitchService(
        projects=deps.projects, sites=deps.sites, active_context=deps.active_context
    )
    res = await svc.select_active_context(
        organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR, project_id=seed.PROJ_ALPHA
    )
    assert res.is_err
    assert res.error.error_code == ErrorCode.PROJECT_NOT_FOUND.value
    # Nothing persisted.
    assert (
        await deps.active_context.get_active_context(
            organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR
        )
        is None
    )


async def test_switch_service_clear():
    deps = seed.build_dependencies()
    svc = ContextSwitchService(
        projects=deps.projects, sites=deps.sites, active_context=deps.active_context
    )
    await svc.select_active_context(
        organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR, project_id=seed.PROJ_MARINA
    )
    await svc.clear_active_context(organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR)
    assert (
        await deps.active_context.get_active_context(
            organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR
        )
        is None
    )


# -- Redis active context store (against FakeRedis) --------------------------


async def test_redis_active_context_roundtrip_and_expiry():
    from mesiri.infrastructure.redis.client import FakeRedis

    clock_time = {"now": datetime(2026, 1, 1, tzinfo=UTC)}
    redis = FakeRedis()
    await redis.connect()
    store = RedisActiveContextStore(redis, clock=lambda: clock_time["now"])
    await store.set_active_context(
        organization_id=seed.ABC_ORG,
        user_id=seed.ABC_DIRECTOR,
        project_id=seed.PROJ_MARINA,
        site_id=seed.SITE_BLOCK_A,
        ttl_seconds=60,
    )
    got = await store.get_active_context(organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR)
    assert got.project_id == seed.PROJ_MARINA
    assert got.site_id == seed.SITE_BLOCK_A
    # Expiry enforced explicitly even though FakeRedis has no TTL eviction.
    clock_time["now"] += timedelta(seconds=61)
    assert (
        await store.get_active_context(organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR)
        is None
    )


# -- Correlation propagation -------------------------------------------------


async def test_correlation_preserved_end_to_end():
    r = resolver()
    res = await r.resolve(
        msg(seed.WA_ENGINEER, correlation_id="cor_journey_42", message_id="msg_42"),
        understanding(correlation_id="cor_journey_42", message_id="msg_42"),
    )
    ctx = res.unwrap()
    assert ctx.correlation_id == "cor_journey_42"
    assert ctx.source_message_id == "msg_42"
    assert ctx.causation_id == "msg_42"


async def test_error_carries_correlation():
    r = resolver()
    res = await r.resolve(
        msg(seed.WA_UNKNOWN, correlation_id="cor_err_1"), understanding(correlation_id="cor_err_1")
    )
    assert res.is_err
    assert res.error.correlation_id == "cor_err_1"


# -- No location resolvable --------------------------------------------------


async def test_no_context_returns_unresolved_source_not_error():
    # A director-like user with multiple projects, no default, no explicit/active.
    world = seed.build_world()
    world.preferences = [p for p in world.preferences if p.user_id != seed.USER_DIRECTOR]
    r = ContextResolver(seed.build_dependencies(world))
    res = await r.resolve(msg(seed.WA_DIRECTOR), understanding())
    ctx = res.unwrap()
    assert ctx.context_project_id is None
    assert ctx.context_source == ContextSource.UNRESOLVED
    assert ctx.context_confidence == ContextConfidence.UNRESOLVED
    # Identity still authoritative.
    assert ctx.context_organization_id == seed.ORG_A
    assert ctx.organization_id == canon(seed.ORG_A)
