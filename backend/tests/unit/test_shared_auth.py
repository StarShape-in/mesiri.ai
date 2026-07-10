"""mesiri.domains.shared.auth — unit tests (no DB, no HTTP server).

get_current_user/require_admin/require_platform_admin are plain async
functions taking FastAPI-injected values directly, so they're callable
without a live app.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException

from mesiri.domains.identity.auth_service import ALGORITHM, SECRET_KEY
from mesiri.domains.shared.auth import get_current_user, require_admin, require_platform_admin


def _token(*, role: str = "USER", org: str = "org_1", **extra: str) -> str:
    payload = {
        "sub": "user_1",
        "org": org,
        "role": role,
        "exp": datetime.now(UTC) + timedelta(hours=1),
        **extra,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def test_get_current_user_accepts_valid_token():
    payload = await get_current_user(f"Bearer {_token(role='ADMIN')}")
    assert payload["role"] == "ADMIN"


async def test_get_current_user_rejects_missing_header():
    with pytest.raises(HTTPException) as exc:
        await get_current_user(None)
    assert exc.value.status_code == 401


async def test_get_current_user_rejects_non_bearer_header():
    with pytest.raises(HTTPException) as exc:
        await get_current_user("Basic abc123")
    assert exc.value.status_code == 401


async def test_get_current_user_rejects_invalid_token():
    with pytest.raises(HTTPException) as exc:
        await get_current_user("Bearer not-a-real-jwt")
    assert exc.value.status_code == 401


async def test_require_admin_accepts_admin_role():
    payload = await require_admin(await get_current_user(f"Bearer {_token(role='ADMIN')}"))
    assert payload["role"] == "ADMIN"


async def test_require_admin_rejects_non_admin():
    with pytest.raises(HTTPException) as exc:
        await require_admin(await get_current_user(f"Bearer {_token(role='USER')}"))
    assert exc.value.status_code == 403


async def test_require_platform_admin_accepts_admin_without_org():
    payload = await require_platform_admin(
        await get_current_user(f"Bearer {_token(role='ADMIN', org='')}")
    )
    assert payload["role"] == "ADMIN"


async def test_require_platform_admin_rejects_tenant_admin_with_org():
    """The exact regression this dependency exists to close: a tenant's own
    org ADMIN must not be treated as a platform-wide operator."""
    with pytest.raises(HTTPException) as exc:
        await require_platform_admin(
            await get_current_user(f"Bearer {_token(role='ADMIN', org='org_1')}")
        )
    assert exc.value.status_code == 403


async def test_require_platform_admin_rejects_non_admin_role():
    with pytest.raises(HTTPException) as exc:
        await require_platform_admin(
            await get_current_user(f"Bearer {_token(role='USER', org='')}")
        )
    assert exc.value.status_code == 403
