"""Integration tests for POST /auth/change-password.

The endpoint's auth check (a valid token is required at all) is already
covered by backend/tests/unit/test_shared_auth.py's get_current_user tests;
these focus on what needs a live database -- verifying the current password
against the real hash and persisting the new one.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from auth import router as auth_router
from mesiri.domains.identity.auth_service import ALGORITHM, SECRET_KEY

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
    monkeypatch.setattr(auth_router, "get_engine", lambda: test_engine)


async def _seed_user(test_engine: AsyncEngine, *, password: str) -> uuid.UUID:
    user_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO users (id, organization_id, email, hashed_password, full_name, "
                "role, status, created_at, updated_at) "
                "VALUES (:id, NULL, :email, :hashed, 'Test User', 'ADMIN', 'active', now(), now())"
            ),
            {
                "id": user_id,
                "email": f"{user_id}@example.com",
                "hashed": auth_router._hash_pw(password),
            },
        )
    return user_id


def _token_for(user_id: uuid.UUID) -> str:
    payload = {
        "sub": str(user_id),
        "org": "",
        "role": "ADMIN",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def test_change_password_rejects_wrong_current_password(test_engine: AsyncEngine, clean_db):
    user_id = await _seed_user(test_engine, password="correct-password")

    with pytest.raises(HTTPException) as exc:
        await auth_router.change_password(
            auth_router.ChangePassword(
                current_password="wrong-password", new_password="new-password-1"
            ),
            authorization=f"Bearer {_token_for(user_id)}",
        )
    assert exc.value.status_code == 401


async def test_change_password_persists_new_hash(test_engine: AsyncEngine, clean_db):
    user_id = await _seed_user(test_engine, password="correct-password")

    await auth_router.change_password(
        auth_router.ChangePassword(
            current_password="correct-password", new_password="new-password-1"
        ),
        authorization=f"Bearer {_token_for(user_id)}",
    )

    async with test_engine.connect() as conn:
        row = (
            await conn.execute(
                sa.text("SELECT hashed_password FROM users WHERE id = :id"), {"id": user_id}
            )
        ).first()
    assert auth_router._verify_pw("new-password-1", row.hashed_password)
    assert not auth_router._verify_pw("correct-password", row.hashed_password)
