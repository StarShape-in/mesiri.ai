"""M4 Context Foundation — live Postgres + Redis integration tests.

Skipped by default (marker ``integration``). Run against the docker stack:

    make dev && make migrate && uv run pytest -m integration

They prove the real PostgreSQL repositories and the Redis active-context store
behave identically to the fakes: tenant isolation holds, active context persists
across a fresh store instance ("restart"), TTL expiry is enforced, and the full
resolver produces a ResolvedContext. AI providers are never called (the
UnderstandingResult is a fixture).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from context import seed
from context.identity_bridge import build_fake_bridge_from_seed, deterministic_canonical_uuid as canon
from context.active_context import RedisActiveContextStore
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
from mesiri_contracts.assistant.candidates import EquipmentUsageCandidate
from mesiri_contracts.assistant.context_enums import ContextSource
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import (
    NormalizedMessage,
    ReplyContext,
    SenderInfo,
)
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.common.errors import ErrorCode

pytestmark = pytest.mark.integration


# -- Fixtures ----------------------------------------------------------------

@pytest.fixture
async def engine():
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    settings = Settings()
    eng = create_async_engine(settings.postgres.dsn())
    world = seed.build_world()
    async with eng.begin() as conn:
        await _clear(conn, text)
        await _seed(conn, text, world)
    yield eng
    async with eng.begin() as conn:
        await _clear(conn, text)
    await eng.dispose()


@pytest.fixture
async def redis():
    client = RedisClient(Settings().redis)
    await client.connect()
    yield client
    await client.disconnect()


async def _clear(conn, text) -> None:
    for tbl in (
        "user_context_preferences", "site_memberships", "project_memberships",
        "context_sites", "context_projects", "role_permissions", "membership_roles",
        "permissions", "roles", "organization_memberships", "external_identities",
        "context_users", "context_organizations",
    ):
        await conn.execute(text(f"DELETE FROM {tbl}"))


async def _seed(conn, text, world: seed.SeedWorld) -> None:
    for o in world.organizations:
        await conn.execute(
            text("INSERT INTO context_organizations (id, name, is_active) VALUES (:i, :n, :a)"),
            {"i": o.organization_id, "n": o.organization_id, "a": o.is_active},
        )
    for u in world.users:
        await conn.execute(
            text("INSERT INTO context_users (id, is_active, locale, timezone) "
                 "VALUES (:i, :a, :l, :t)"),
            {"i": u.user_id, "a": u.is_active, "l": u.locale, "t": u.timezone},
        )
    for n, i in enumerate(world.identities):
        await conn.execute(
            text("INSERT INTO external_identities (id, provider, external_subject, user_id) "
                 "VALUES (:id, :p, :s, :u)"),
            {"id": f"eid_{n}", "p": i.provider, "s": i.external_subject, "u": i.user_id},
        )
    for m in world.memberships:
        await conn.execute(
            text("INSERT INTO organization_memberships (id, organization_id, user_id, is_active) "
                 "VALUES (:id, :o, :u, :a)"),
            {"id": m.membership_id, "o": m.organization_id, "u": m.user_id, "a": m.is_active},
        )
    # Roles + permissions.
    perms = {p for plist in world.membership_permissions.values() for p in plist}
    for p in sorted(perms):
        await conn.execute(
            text("INSERT INTO permissions (id, code) VALUES (:i, :c)"),
            {"i": f"perm_{p}", "c": p},
        )
    for mem_id, role_ids in world.membership_roles.items():
        org = next(m.organization_id for m in world.memberships if m.membership_id == mem_id)
        for role_id in role_ids:
            await conn.execute(
                text("INSERT INTO roles (id, organization_id, name) VALUES (:i, :o, :n) "
                     "ON CONFLICT (id) DO NOTHING"),
                {"i": role_id, "o": org, "n": role_id},
            )
            await conn.execute(
                text("INSERT INTO membership_roles (membership_id, role_id) VALUES (:m, :r)"),
                {"m": mem_id, "r": role_id},
            )
            for p in world.membership_permissions.get(mem_id, []):
                await conn.execute(
                    text("INSERT INTO role_permissions (role_id, permission_id) "
                         "VALUES (:r, :p) ON CONFLICT DO NOTHING"),
                    {"r": role_id, "p": f"perm_{p}"},
                )
    for p in world.projects:
        await conn.execute(
            text("INSERT INTO context_projects (id, organization_id, name, is_active) "
                 "VALUES (:i, :o, :n, :a)"),
            {"i": p.project_id, "o": p.organization_id, "n": p.name, "a": p.is_active},
        )
    for s in world.sites:
        await conn.execute(
            text("INSERT INTO context_sites (id, project_id, organization_id, name, is_active) "
                 "VALUES (:i, :p, :o, :n, :a)"),
            {"i": s.site_id, "p": s.project_id, "o": s.organization_id, "n": s.name, "a": s.is_active},
        )
    for user_id, project_ids in world.project_access.items():
        for pid in project_ids:
            await conn.execute(
                text("INSERT INTO project_memberships (user_id, project_id) VALUES (:u, :p)"),
                {"u": user_id, "p": pid},
            )
    for pref in world.preferences:
        await conn.execute(
            text("INSERT INTO user_context_preferences "
                 "(organization_id, user_id, default_project_id, default_site_id, locale, timezone) "
                 "VALUES (:o, :u, :dp, :ds, :l, :t)"),
            {"o": pref.organization_id, "u": pref.user_id, "dp": pref.default_project_id,
             "ds": pref.default_site_id, "l": pref.locale, "t": pref.timezone},
        )


def _deps(engine, active_store) -> ContextDependencies:
    return ContextDependencies(
        identities=PostgresExternalIdentityRepository(engine),
        memberships=PostgresMembershipRepository(engine),
        roles=PostgresRolePermissionRepository(engine),
        projects=PostgresProjectRepository(engine),
        sites=PostgresSiteRepository(engine),
        preferences=PostgresContextPreferenceRepository(engine),
        active_context=active_store,
        reply_context=NullReplyContextProvider(),
        workflow_context=NullWorkflowContextProvider(),
        bridge=build_fake_bridge_from_seed(),
    )


def _msg(wa_id, **kw):
    reply_to = kw.get("reply_to")
    return NormalizedMessage(
        message_id=kw.get("message_id", "msg_i"),
        correlation_id=kw.get("correlation_id", "cor_i"),
        channel="whatsapp",
        sender=SenderInfo(wa_id=wa_id),
        timestamp=datetime.now(UTC),
        modality=InputModality.TEXT,
        text="hi",
        reply_context=ReplyContext(replied_to_message_id=reply_to) if reply_to else None,
    )


def _und(fields=None):
    cands = [EquipmentUsageCandidate(fields=fields)] if fields else []
    return UnderstandingResult(
        source_message_id="msg_i", correlation_id="cor_i",
        input_modality=InputModality.TEXT, candidates=cands,
    )


# -- Tests -------------------------------------------------------------------

async def test_identity_and_membership_lookup(engine, redis):
    store = RedisActiveContextStore(redis)
    r = ContextResolver(_deps(engine, store))
    ctx = (await r.resolve(_msg(seed.WA_ENGINEER), _und())).unwrap()
    assert ctx.context_organization_id == seed.ORG_A
    assert ctx.organization_id == canon(seed.ORG_A)
    assert "expense.create" in ctx.permissions


async def test_project_authorization_and_isolation(engine, redis):
    store = RedisActiveContextStore(redis)
    r = ContextResolver(_deps(engine, store))
    # Same name "Project Alpha" exists in two orgs; Org B user must get Org B's.
    ctx = (await r.resolve(
        _msg(seed.WA_ORGB), _und({"project_name": "Project Alpha"})
    )).unwrap()
    assert ctx.context_organization_id == seed.ORG_B
    assert ctx.context_project_id == seed.PROJ_ALPHA_B


async def test_cross_org_project_id_not_found(engine, redis):
    store = RedisActiveContextStore(redis)
    r = ContextResolver(_deps(engine, store))
    res = await r.resolve(_msg(seed.WA_ORGB), _und({"project_id": seed.PROJ_ALPHA}))
    assert res.is_err and res.error.error_code == ErrorCode.PROJECT_NOT_FOUND.value


async def test_active_context_persists_and_survives_restart(engine, redis):
    store = RedisActiveContextStore(redis)
    await store.set_active_context(
        organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR,
        project_id=seed.PROJ_MARINA, site_id=None, ttl_seconds=3600,
    )
    # New store instance over the same Redis backend == application restart.
    store2 = RedisActiveContextStore(redis)
    r = ContextResolver(_deps(engine, store2))
    ctx = (await r.resolve(_msg(seed.WA_ABC_DIRECTOR), _und())).unwrap()
    assert ctx.context_project_id == seed.PROJ_MARINA
    assert ctx.context_source == ContextSource.ACTIVE_CONTEXT
    await store2.clear_active_context(organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR)


async def test_active_context_ttl_expiry(engine, redis):
    clock = {"now": datetime.now(UTC)}
    store = RedisActiveContextStore(redis, clock=lambda: clock["now"])
    await store.set_active_context(
        organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR,
        project_id=seed.PROJ_MARINA, site_id=None, ttl_seconds=60,
    )
    clock["now"] += timedelta(seconds=61)
    assert await store.get_active_context(
        organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR
    ) is None


async def test_full_resolution_produces_resolved_context(engine, redis):
    store = RedisActiveContextStore(redis)
    r = ContextResolver(_deps(engine, store))
    ctx = (await r.resolve(
        _msg(seed.WA_ABC_DIRECTOR), _und({"project_name": "Marina Tower"})
    )).unwrap()
    assert ctx.version == "v2"
    assert ctx.context_project_id == seed.PROJ_MARINA
    assert ctx.context_source == ContextSource.MESSAGE_EXPLICIT


async def test_postgres_unavailable_maps_to_dependency_error():
    from sqlalchemy.ext.asyncio import create_async_engine

    bad = create_async_engine("postgresql+asyncpg://bad:bad@127.0.0.1:1/none")
    repo = PostgresExternalIdentityRepository(bad)
    from mesiri_contracts.common.errors import MesiriError

    with pytest.raises(MesiriError) as exc:
        await repo.find_identity(provider="whatsapp", external_subject="x")
    assert exc.value.error_code == ErrorCode.POSTGRES_UNAVAILABLE.value
    await bad.dispose()
