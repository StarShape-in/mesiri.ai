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
async def test_understand_voice_calls_gemini_directly_when_voice_routes_to_gemini():
    """The real win: when voice is routed to Gemini, understand_voice() must
    call the adapter's own merged transcribe+extract method directly -- one
    call, not two -- rather than composing transcribe()+extract() itself."""
    from mesiri_ai.models import ExtractionResult

    settings = FakeSettings()
    db = MagicMock()
    if hasattr(db, "transaction"):
        del db.transaction
    # FakeSettings' env defaults route voice to sarvam (see _resolve_config's
    # fallback derivation) -- force gemini explicitly via the Redis cache so
    # this test actually exercises the branch it's named for.
    cached_config = {
        "routing": {
            "voice": {"provider_id": "gemini", "model": "gemini-test"},
            "extraction": {"provider_id": "fake", "model": ""},
            "vision": {"provider_id": "fake", "model": ""},
            "translation": {"provider_id": "fake", "model": ""},
        },
        "secrets": {"gemini": {"api_key": "gemini-key", "base_url": None}},
    }
    redis = AsyncMock()
    redis.get.return_value = json.dumps(cached_config)

    resolver = DynamicAIProviderResolver(db, redis, settings)

    combined = ExtractionResult(
        transcript="hi",
        translated_text="hi",
        semantic_type="unknown",
        model="gemini-test",
        latency_ms=900.0,
    )

    class FakeGeminiProvider:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def understand_voice(self, audio, **kwargs):
            return combined

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "mesiri_ai.resolver._build_gemini_provider", lambda *a, **kw: FakeGeminiProvider()
        )
        result = await resolver.understand_voice(b"audio-bytes", correlation_id="cor_1")

    assert result is combined


@pytest.mark.anyio
async def test_understand_voice_falls_back_to_transcribe_then_extract_for_non_gemini_voice():
    """Sarvam (or any non-Gemini voice provider) has no extraction
    capability of its own to merge with -- understand_voice() must fall back
    to composing transcribe() then extract() internally, and the caller gets
    the same ExtractionResult shape back either way."""
    from mesiri_ai.models import ExtractionResult, SpeechResult

    settings = FakeSettings()
    db = MagicMock()
    if hasattr(db, "transaction"):
        del db.transaction

    cached_config = {
        "routing": {
            "voice": {"provider_id": "fake", "model": ""},
            "extraction": {"provider_id": "fake", "model": ""},
            "vision": {"provider_id": "fake", "model": ""},
            "translation": {"provider_id": "fake", "model": ""},
        },
        "secrets": {"gemini": {"api_key": None, "base_url": None}},
    }
    redis = AsyncMock()
    redis.get.return_value = json.dumps(cached_config)

    resolver = DynamicAIProviderResolver(db, redis, settings)

    async def _fake_transcribe(audio, **kwargs):
        return SpeechResult(
            transcript="ஜேசிபி ஓடியது",
            translated_text="the JCB ran",
            detected_language="Tamil",
            latency_ms=100.0,
        )

    async def _fake_extract(text, **kwargs):
        return ExtractionResult(
            semantic_type="equipment_usage",
            fields={"equipment_name": "JCB"},
            latency_ms=150.0,
        )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(resolver, "transcribe", _fake_transcribe)
        mp.setattr(resolver, "extract", _fake_extract)
        result = await resolver.understand_voice(b"audio-bytes", correlation_id="cor_2")

    assert result.transcript == "ஜேசிபி ஓடியது"
    assert result.translated_text == "the JCB ran"
    assert result.detected_language == "Tamil"
    assert result.semantic_type == "equipment_usage"
    assert result.fields == {"equipment_name": "JCB"}
    # Two real calls happened -- their latencies are summed so the one
    # provider_execution row a caller logs for understand_voice reflects
    # the true total cost.
    assert result.latency_ms == 250.0


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


@pytest.mark.anyio
async def test_decompose_reuses_the_extraction_route_deepseek_by_default():
    """docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §9: decompose() reuses
    the existing extraction route rather than a new routing capability --
    FakeSettings has no explicit routing config, so it falls through to
    the same deepseek-by-default extraction route generate_json's sibling
    test exercises."""
    from mesiri_ai.models import DecompositionResult

    settings = FakeSettings()
    db = MagicMock()
    if hasattr(db, "transaction"):
        del db.transaction
    redis = AsyncMock()
    redis.get.return_value = None

    resolver = DynamicAIProviderResolver(db, redis, settings)

    class FakeDeepSeekProvider:
        provider = "deepseek"

        def __init__(self, *args, **kwargs) -> None:
            pass

        async def decompose(self, text, *, correlation_id=None):
            return DecompositionResult(
                is_multi_intent=True,
                segments=["create a project called Starship", "create a site called Site A"],
                provider="deepseek",
            )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "mesiri_ai.resolver._build_deepseek_provider",
            lambda *a, **kw: FakeDeepSeekProvider(),
        )
        result = await resolver.decompose("Starship then Site A", correlation_id="cor_3")

    assert result.is_multi_intent is True
    assert result.segments == [
        "create a project called Starship",
        "create a site called Site A",
    ]
    assert result.provider == "deepseek"


@pytest.mark.anyio
async def test_decompose_falls_back_to_the_configured_fallback_provider_on_failure():
    from mesiri_ai.core.errors import malformed_output
    from mesiri_ai.models import DecompositionResult

    settings = FakeSettings()
    db = MagicMock()
    redis = AsyncMock()
    redis.get.return_value = json.dumps(
        {
            "routing": {
                "voice": {"provider_id": "sarvam", "model": "saaras:v2.5"},
                "extraction": {
                    "provider_id": "deepseek",
                    "model": "deepseek-primary",
                    "fallback_provider_id": "gemini",
                    "fallback_model": "gemini-fallback",
                },
                "vision": {"provider_id": "gemini", "model": "gemini-vision"},
            },
            "secrets": {
                "gemini": {"api_key": "gemini-key"},
                "deepseek": {"api_key": "ds-key"},
                "sarvam": {"api_key": "sarvam-key"},
            },
        }
    )

    resolver = DynamicAIProviderResolver(db, redis, settings)

    class FailingDeepSeekProvider:
        provider = "deepseek"

        def __init__(self, *args, **kwargs) -> None:
            pass

        async def decompose(self, text, *, correlation_id=None):
            raise malformed_output("deepseek", "boom", correlation_id=correlation_id)

    class FallbackGeminiProvider:
        provider = "gemini"

        def __init__(self, *args, **kwargs) -> None:
            pass

        async def decompose(self, text, *, correlation_id=None):
            return DecompositionResult(is_multi_intent=False, provider="gemini")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "mesiri_ai.resolver._build_deepseek_provider",
            lambda *a, **kw: FailingDeepSeekProvider(),
        )
        mp.setattr(
            "mesiri_ai.resolver._build_gemini_provider",
            lambda *a, **kw: FallbackGeminiProvider(),
        )
        result = await resolver.decompose("some message", correlation_id="cor_4")

    assert result.provider == "gemini"
    assert result.is_multi_intent is False
