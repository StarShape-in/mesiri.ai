"""Integration tests for admin.platform_users_router.

These call the route handler functions directly (they're plain async
functions) against a real Postgres engine -- the auth boundary itself
(require_platform_admin) is already covered by
backend/tests/unit/test_shared_auth.py, so these focus on what actually
needs a live database: the self-deactivation and last-active-admin
guardrails, and that created accounts always land with organization_id
NULL. Requires docker/CI environment with database (same convention as
backend/tests/integration/test_postgres_project_repository.py).
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from admin import platform_users_router as router_module

pytestmark = pytest.mark.integration


@pytest.fixture
async def test_engine():
    from mesiri.bootstrap.settings import Settings

    settings = Settings()
    engine = create_async_engine(settings.postgres.dsn(), echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def clean_db(test_engine: AsyncEngine):
    async with test_engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM users WHERE organization_id IS NULL"))
    yield


@pytest.fixture(autouse=True)
def _use_test_engine(test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(router_module, "get_engine", lambda: test_engine)


async def _seed_platform_admin(
    test_engine: AsyncEngine, *, email: str, status: str = "active"
) -> uuid.UUID:
    user_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO users (id, organization_id, email, hashed_password, full_name, "
                "role, status, created_at, updated_at) "
                "VALUES (:id, NULL, :email, 'x', 'Seed Admin', 'ADMIN', :status, now(), now())"
            ),
            {"id": user_id, "email": email, "status": status},
        )
    return user_id


async def test_create_platform_user_has_no_organization_id(test_engine: AsyncEngine, clean_db):
    result = await router_module.create_platform_user(
        router_module.PlatformUserCreate(
            email="new-admin@example.com", password="a-strong-password", full_name="New Admin"
        ),
        _admin={"sub": "someone"},
    )

    assert result.status == "active"
    async with test_engine.connect() as conn:
        row = (
            await conn.execute(
                sa.text("SELECT organization_id, role FROM users WHERE id = :id"),
                {"id": result.id},
            )
        ).first()
    assert row.organization_id is None
    assert row.role == "ADMIN"


async def test_create_platform_user_rejects_duplicate_email(test_engine: AsyncEngine, clean_db):
    await _seed_platform_admin(test_engine, email="dup@example.com")

    with pytest.raises(HTTPException) as exc:
        await router_module.create_platform_user(
            router_module.PlatformUserCreate(
                email="dup@example.com", password="a-strong-password", full_name="Dup"
            ),
            _admin={"sub": "someone"},
        )
    assert exc.value.status_code == 400


async def test_update_blocks_self_deactivation(test_engine: AsyncEngine, clean_db):
    admin_id = await _seed_platform_admin(test_engine, email="self@example.com")
    # A second active admin exists, so this isn't blocked by the last-admin rule --
    # only the self-deactivation rule should trigger.
    await _seed_platform_admin(test_engine, email="other@example.com")

    with pytest.raises(HTTPException) as exc:
        await router_module.update_platform_user(
            admin_id,
            router_module.PlatformUserUpdate(status="inactive"),
            admin={"sub": str(admin_id)},
        )
    assert exc.value.status_code == 400
    assert "own account" in exc.value.detail


async def test_update_blocks_deactivating_last_active_admin(test_engine: AsyncEngine, clean_db):
    target_id = await _seed_platform_admin(test_engine, email="last@example.com")
    caller_id = uuid.uuid4()  # a different (non-existent) caller, to isolate this rule

    with pytest.raises(HTTPException) as exc:
        await router_module.update_platform_user(
            target_id,
            router_module.PlatformUserUpdate(status="suspended"),
            admin={"sub": str(caller_id)},
        )
    assert exc.value.status_code == 400
    assert "last active" in exc.value.detail


async def test_update_allows_deactivating_when_another_active_admin_remains(
    test_engine: AsyncEngine, clean_db
):
    target_id = await _seed_platform_admin(test_engine, email="target@example.com")
    await _seed_platform_admin(test_engine, email="another@example.com")
    caller_id = uuid.uuid4()

    result = await router_module.update_platform_user(
        target_id,
        router_module.PlatformUserUpdate(status="suspended"),
        admin={"sub": str(caller_id)},
    )
    assert result.status == "suspended"


async def test_update_full_name_and_password_do_not_require_status(
    test_engine: AsyncEngine, clean_db
):
    target_id = await _seed_platform_admin(test_engine, email="rename@example.com")
    caller_id = uuid.uuid4()

    result = await router_module.update_platform_user(
        target_id,
        router_module.PlatformUserUpdate(full_name="Renamed Admin", new_password="new-password-1"),
        admin={"sub": str(caller_id)},
    )
    assert result.full_name == "Renamed Admin"
    assert result.status == "active"  # untouched


async def test_list_platform_users_excludes_tenant_admins(test_engine: AsyncEngine, clean_db):
    await _seed_platform_admin(test_engine, email="platform@example.com")
    org_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) "
                "VALUES (:id, 'Tenant Org', 'local', 'default', 'active', now(), now())"
            ),
            {"id": org_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO users (id, organization_id, email, hashed_password, full_name, "
                "role, status, created_at, updated_at) "
                "VALUES (:id, :org_id, 'tenant-admin@example.com', 'x', 'Tenant Admin', "
                "'ADMIN', 'active', now(), now())"
            ),
            {"id": uuid.uuid4(), "org_id": org_id},
        )

    try:
        result = await router_module.list_platform_users(_admin={"sub": "someone"})
        emails = {u.email for u in result}
        assert "platform@example.com" in emails
        assert "tenant-admin@example.com" not in emails
    finally:
        async with test_engine.begin() as conn:
            await conn.execute(sa.text("DELETE FROM users WHERE organization_id = :id"), {"id": org_id})
            await conn.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})
