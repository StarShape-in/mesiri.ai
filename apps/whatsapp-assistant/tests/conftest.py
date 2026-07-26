"""Shared test fixtures for WhatsApp ingress."""

from __future__ import annotations

import hashlib
import hmac
import importlib.machinery
import importlib.util
import json
import os
import sys
import sysconfig
from typing import Any

_stdlib_dir = sysconfig.get_path("stdlib")
_platform_py = os.path.join(_stdlib_dir, "platform.py")
if os.path.isfile(_platform_py):
    _loader = importlib.machinery.SourceFileLoader("_stdlib_platform", _platform_py)
    _spec = importlib.util.spec_from_loader("_stdlib_platform", _loader)
    _mod = importlib.util.module_from_spec(_spec)
    _loader.exec_module(_mod)
    sys.modules["platform"] = _mod

import pytest
from httpx import ASGITransport, AsyncClient

from runtime.dependencies import Settings
from runtime.lifecycle import create_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    """Return test settings for WhatsApp ingress."""
    return Settings(
        verify_token="test-verify-token",
        app_secret="test-app-secret",
        access_token="test-access-token",
        api_version="v21.0",
        media_download_dir=str(tmp_path / "media"),
    )


@pytest.fixture
def app(settings: Settings):
    """Return a configured FastAPI application."""
    return create_app(settings=settings)


@pytest.fixture
async def client(app):
    """Return an async HTTP client bound to the FastAPI application."""
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as async_client:
            yield async_client


def sign_payload(payload: dict[str, Any], app_secret: str) -> tuple[str, bytes]:
    """Generate a Meta-compatible webhook signature header and canonical body."""
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}", body
