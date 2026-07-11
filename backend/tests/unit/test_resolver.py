"""Tests for the Dynamic AI Provider Resolver."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from mesiri_ai.resolver import DynamicAIProviderResolver
from mesiri_contracts.common.errors import MesiriError


class FakeSettings:
    class Section:
        def __init__(self, api_key=None, model="default-model", base_url=None):
            from pydantic import SecretStr

            self.api_key = SecretStr(api_key) if api_key else None
            self.model = model
            self.base_url = base_url
            self.timeout_seconds = 10.0
            self.max_retries = 2

    def __init__(self):
        self.gemini = self.Section(api_key="gemini-key", model="gemini-default")
        self.deepseek = self.Section(
            api_key="ds-key", model="ds-default", base_url="https://api.deepseek.com"
        )
        self.sarvam = self.Section(api_key="sarvam-key", model="saaras:v2.5")


@pytest.mark.anyio
async def test_resolver_falls_back_to_env_settings():
    settings = FakeSettings()
    db = MagicMock()
    if hasattr(db, "transaction"):
        del db.transaction

    redis = AsyncMock()
    redis.get.return_value = None

    resolver = DynamicAIProviderResolver(db, redis, settings)
    config = await resolver._resolve_config()

    assert config["routing"]["voice"]["provider_id"] == "sarvam"
    assert config["routing"]["extraction"]["provider_id"] == "deepseek"
    assert config["secrets"]["gemini"]["api_key"] == "gemini-key"
    assert config["secrets"]["deepseek"]["api_key"] == "ds-key"
    assert config["secrets"]["sarvam"]["api_key"] == "sarvam-key"


@pytest.mark.anyio
async def test_resolver_uses_redis_cache():
    settings = FakeSettings()
    db = MagicMock()
    redis = AsyncMock()

    cached_config = {
        "routing": {
            "voice": {"provider_id": "fake", "model": ""},
            "extraction": {"provider_id": "gemini", "model": "gemini-custom"},
            "vision": {"provider_id": "fake", "model": ""},
            "translation": {"provider_id": "fake", "model": ""},
        },
        "secrets": {
            "gemini": {"api_key": "cached-gemini", "base_url": None},
        },
    }
    redis.get.return_value = json.dumps(cached_config)

    resolver = DynamicAIProviderResolver(db, redis, settings)
    config = await resolver._resolve_config()

    assert config["routing"]["extraction"]["provider_id"] == "gemini"
    assert config["routing"]["extraction"]["model"] == "gemini-custom"
    assert config["secrets"]["gemini"]["api_key"] == "cached-gemini"
    assert db.transaction.call_count == 0


@pytest.mark.anyio
async def test_resolver_queries_database_on_redis_cache_miss():
    settings = FakeSettings()
    redis = AsyncMock()
    redis.get.return_value = None

    db = MagicMock()
    conn = AsyncMock()

    active_routes = {
        "voice": {"provider_id": "fake", "model": ""},
        "extraction": {"provider_id": "deepseek", "model": "deepseek-custom"},
    }
    provider_secrets = {
        "deepseek": {"api_key": "db-deepseek-key", "base_url": "https://custom.deepseek.com"},
    }

    class AsyncContextManagerMock:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    db.transaction.return_value = AsyncContextManagerMock()

    mock_repo_instance = MagicMock()
    mock_repo_instance.get_active_routes = AsyncMock(return_value=active_routes)
    mock_repo_instance.get_provider_secrets = AsyncMock(return_value=provider_secrets)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "mesiri.infrastructure.postgres.repositories.ai_config.PostgresAIConfigRepository",
            lambda c: mock_repo_instance,
        )

        resolver = DynamicAIProviderResolver(db, redis, settings)
        config = await resolver._resolve_config()

        assert config["routing"]["extraction"]["provider_id"] == "deepseek"
        assert config["routing"]["extraction"]["model"] == "deepseek-custom"
        assert config["secrets"]["deepseek"]["api_key"] == "db-deepseek-key"
        assert config["secrets"]["deepseek"]["base_url"] == "https://custom.deepseek.com"
        redis.set.assert_called_once()


@pytest.mark.anyio
async def test_generate_json_falls_back_to_gemini_even_when_extraction_routes_elsewhere():
    """Extraction is routed to deepseek by default in FakeSettings (deepseek key
    present), but generate_json (used by the interaction slow-path correction
    classifier -- only GeminiProvider implements it) must still reach Gemini
    directly as long as a Gemini key exists at all."""
    settings = FakeSettings()
    db = MagicMock()
    if hasattr(db, "transaction"):
        del db.transaction
    redis = AsyncMock()
    redis.get.return_value = None

    resolver = DynamicAIProviderResolver(db, redis, settings)

    class FakeGeminiProvider:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def generate_json(self, system_prompt, user_prompt, *, correlation_id=None):
            return '[{"intent": "correction", "segment_text": "40 bags"}]'

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "mesiri_ai.resolver._build_gemini_provider", lambda *a, **kw: FakeGeminiProvider()
        )
        result = await resolver.generate_json("sys prompt", "user prompt", correlation_id="cor_1")

    assert result == '[{"intent": "correction", "segment_text": "40 bags"}]'


@pytest.mark.anyio
async def test_generate_json_raises_without_any_gemini_key():
    settings = FakeSettings()
    settings.gemini = FakeSettings.Section(api_key=None)
    db = MagicMock()
    if hasattr(db, "transaction"):
        del db.transaction
    redis = AsyncMock()
    redis.get.return_value = None

    resolver = DynamicAIProviderResolver(db, redis, settings)
    with pytest.raises(MesiriError):
        await resolver.generate_json("sys prompt", "user prompt")
