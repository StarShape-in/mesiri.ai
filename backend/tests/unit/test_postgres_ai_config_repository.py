"""Unit tests for PostgresAIConfigRepository using mocked DB connection."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mesiri.infrastructure.postgres.repositories.ai_config import PostgresAIConfigRepository


@pytest.mark.anyio
async def test_get_active_routes():
    conn = AsyncMock()

    # Mock row output (include new fallback columns)
    row1 = MagicMock()
    row1.capability = "voice"
    row1.provider_id = "sarvam"
    row1.model = "saaras:v2.5"
    row1.fallback_provider_id = None
    row1.fallback_model = None

    row2 = MagicMock()
    row2.capability = "extraction"
    row2.provider_id = "gemini"
    row2.model = "gemini-2.5-flash"
    row2.fallback_provider_id = "deepseek"
    row2.fallback_model = "deepseek-chat"

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [row1, row2]
    conn.execute.return_value = mock_result

    repo = PostgresAIConfigRepository(conn)
    routes = await repo.get_active_routes()

    assert routes == {
        "voice": {
            "provider_id": "sarvam",
            "model": "saaras:v2.5",
            "fallback_provider_id": None,
            "fallback_model": None,
        },
        "extraction": {
            "provider_id": "gemini",
            "model": "gemini-2.5-flash",
            "fallback_provider_id": "deepseek",
            "fallback_model": "deepseek-chat",
        },
    }
    assert conn.execute.call_count == 1


@pytest.mark.anyio
async def test_get_provider_secrets():
    conn = AsyncMock()

    row1 = MagicMock()
    row1.provider_id = "gemini"
    row1.api_key = "gemini-key-secret"
    row1.base_url = None

    row2 = MagicMock()
    row2.provider_id = "deepseek"
    row2.api_key = "deepseek-key-secret"
    row2.base_url = "https://custom.deepseek.com"

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [row1, row2]
    conn.execute.return_value = mock_result

    repo = PostgresAIConfigRepository(conn)
    secrets = await repo.get_provider_secrets()

    assert secrets == {
        "gemini": {"api_key": "gemini-key-secret", "base_url": None},
        "deepseek": {"api_key": "deepseek-key-secret", "base_url": "https://custom.deepseek.com"},
    }
    assert conn.execute.call_count == 1


@pytest.mark.anyio
async def test_update_active_route():
    conn = AsyncMock()
    repo = PostgresAIConfigRepository(conn)

    await repo.update_active_route("voice", "fake", "fake-model")

    # Ensure execute was called with upsert statement
    assert conn.execute.call_count == 1


@pytest.mark.anyio
async def test_update_provider_secret():
    conn = AsyncMock()
    repo = PostgresAIConfigRepository(conn)

    await repo.update_provider_secret("deepseek", "new-key", "https://api.deepseek.com")

    assert conn.execute.call_count == 1
