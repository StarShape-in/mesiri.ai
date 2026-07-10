"""Dynamic AI Provider Resolver Proxy (M3/M9).

Resolves which AI model/provider to use for each capability dynamically at runtime.
Uses Redis caching to maintain sub-millisecond lookup latency, falling back to
PostgreSQL config tables and then environment settings.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mesiri_contracts.common.errors import MesiriError
from mesiri_ai import fixtures
from mesiri_ai.models import ExtractionResult, SpeechResult, TranslationResult, VisionResult

logger = logging.getLogger(__name__)


class DynamicAIProviderResolver:
    """Dynamic resolver implementing AI ports.

    Queries Redis/DB to route calls to the active provider dynamically.
    """

    provider = "dynamic"

    def __init__(self, db: Any, redis_client: Any, settings: Any) -> None:
        self._db = db
        self._redis = redis_client
        self._settings = settings

    async def _resolve_config(self) -> dict[str, Any]:
        """Resolve active routing and credentials from Redis -> DB -> Env."""
        # 1. Try Redis cache
        cache_key = "mesiri:ai:config"
        try:
            # Check if redis client has a valid connect state and supports get
            if self._redis and hasattr(self._redis, "get"):
                cached = await self._redis.get(cache_key)
                if cached:
                    return json.loads(cached)
        except Exception as exc:
            logger.warning("Failed to read AI config from Redis: %s", exc)

        # Default fallback config derived from environment Settings
        config = {
            "routing": {
                "voice": {
                    "provider_id": "sarvam" if self._settings.sarvam.api_key else "fake",
                    "model": "saaras:v2.5",
                },
                "extraction": {
                    "provider_id": (
                        "deepseek"
                        if self._settings.deepseek.api_key
                        else ("gemini" if self._settings.gemini.api_key else "fake")
                    ),
                    "model": (
                        self._settings.deepseek.model
                        if self._settings.deepseek.api_key
                        else self._settings.gemini.model
                    ),
                },
                "vision": {
                    "provider_id": "gemini" if self._settings.gemini.api_key else "fake",
                    "model": self._settings.gemini.model,
                },
                "translation": {
                    "provider_id": "gemini" if self._settings.gemini.api_key else "fake",
                    "model": self._settings.gemini.model,
                },
            },
            "secrets": {
                "gemini": {
                    "api_key": (
                        self._settings.gemini.api_key.get_secret_value()
                        if self._settings.gemini.api_key
                        else None
                    ),
                    "base_url": None,
                },
                "deepseek": {
                    "api_key": (
                        self._settings.deepseek.api_key.get_secret_value()
                        if self._settings.deepseek.api_key
                        else None
                    ),
                    "base_url": self._settings.deepseek.base_url,
                },
                "sarvam": {
                    "api_key": (
                        self._settings.sarvam.api_key.get_secret_value()
                        if self._settings.sarvam.api_key
                        else None
                    ),
                    "base_url": None,
                },
            },
        }

        # 2. Try PostgreSQL database if available
        if self._db and hasattr(self._db, "transaction"):
            try:
                from mesiri.infrastructure.postgres.repositories.ai_config import (
                    PostgresAIConfigRepository,
                )

                async with self._db.transaction() as conn:
                    repo = PostgresAIConfigRepository(conn)
                    db_routes = await repo.get_active_routes()
                    db_secrets = await repo.get_provider_secrets()

                # Merge DB routes
                for cap, route in db_routes.items():
                    config["routing"][cap] = {
                        "provider_id": route["provider_id"],
                        "model": route["model"],
                    }

                # Merge DB secrets
                for provider, sec in db_secrets.items():
                    if sec.get("api_key"):
                        config["secrets"][provider]["api_key"] = sec["api_key"]
                    if sec.get("base_url"):
                        config["secrets"][provider]["base_url"] = sec["base_url"]

            except Exception as exc:
                logger.warning("Failed to query DB for AI routing config: %s", exc)

        # 3. Write back to Redis cache
        try:
            if self._redis and hasattr(self._redis, "set"):
                await self._redis.set(cache_key, json.dumps(config))
        except Exception as exc:
            logger.warning("Failed to write AI config to Redis: %s", exc)

        return config

    async def transcribe(
        self,
        audio: bytes,
        *,
        language_hint: str | None = None,
        correlation_id: str | None = None,
    ) -> SpeechResult:
        """Transcribe voice audio."""
        config = await self._resolve_config()
        route = config["routing"].get("voice", {"provider_id": "fake", "model": ""})
        provider_id = route["provider_id"]

        if provider_id == "sarvam":
            from mesiri.bootstrap.settings import SarvamSettings
            from mesiri_ai.adapters.sarvam.adapter import SarvamSpeechProvider

            secret = config["secrets"].get("sarvam", {})
            api_key = secret.get("api_key")
            if not api_key:
                raise MesiriError.configuration(
                    "Sarvam API Key is not configured in environment or database.",
                    code="CONFIG_MISSING",
                )

            # Reconstruct transient settings for adapter
            from pydantic import SecretStr

            settings = SarvamSettings(
                api_key=SecretStr(api_key),
                timeout_seconds=self._settings.sarvam.timeout_seconds,
                max_retries=self._settings.sarvam.max_retries,
            )
            provider = SarvamSpeechProvider(settings)
            return await provider.transcribe(
                audio, language_hint=language_hint, correlation_id=correlation_id
            )

        # Fallback/Fake
        from mesiri_ai.fakes import FakeSpeechProvider

        provider = FakeSpeechProvider(fixtures.MALAYALAM_JCB_SPEECH)
        return await provider.transcribe(
            audio, language_hint=language_hint, correlation_id=correlation_id
        )

    async def extract(
        self,
        text: str,
        *,
        semantic_hint: str | None = None,
        correlation_id: str | None = None,
    ) -> ExtractionResult:
        """Extract structured entities from text."""
        config = await self._resolve_config()
        route = config["routing"].get("extraction", {"provider_id": "fake", "model": ""})
        provider_id = route["provider_id"]
        model = route["model"]

        if provider_id == "gemini":
            from mesiri.bootstrap.settings import GeminiSettings
            from mesiri_ai.adapters.gemini.adapter import GeminiProvider
            from pydantic import SecretStr

            secret = config["secrets"].get("gemini", {})
            api_key = secret.get("api_key")
            if not api_key:
                raise MesiriError.configuration(
                    "Gemini API Key is not configured.", code="CONFIG_MISSING"
                )

            settings = GeminiSettings(
                api_key=SecretStr(api_key),
                model=model or self._settings.gemini.model,
                timeout_seconds=self._settings.gemini.timeout_seconds,
                max_retries=self._settings.gemini.max_retries,
            )
            provider = GeminiProvider(settings)
            return await provider.extract(
                text, semantic_hint=semantic_hint, correlation_id=correlation_id
            )

        elif provider_id == "deepseek":
            from mesiri.bootstrap.settings import DeepSeekSettings
            from mesiri_ai.adapters.deepseek.adapter import DeepSeekExtractionProvider
            from pydantic import SecretStr

            secret = config["secrets"].get("deepseek", {})
            api_key = secret.get("api_key")
            base_url = secret.get("base_url") or "https://api.deepseek.com"
            if not api_key:
                raise MesiriError.configuration(
                    "DeepSeek API Key is not configured.", code="CONFIG_MISSING"
                )

            settings = DeepSeekSettings(
                api_key=SecretStr(api_key),
                model=model or self._settings.deepseek.model,
                base_url=base_url,
                timeout_seconds=self._settings.deepseek.timeout_seconds,
                max_retries=self._settings.deepseek.max_retries,
            )
            provider = DeepSeekExtractionProvider(settings)
            return await provider.extract(
                text, semantic_hint=semantic_hint, correlation_id=correlation_id
            )

        # Fallback/Fake
        from mesiri_ai.fakes import FakeExtractionProvider

        provider = FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION)
        return await provider.extract(
            text, semantic_hint=semantic_hint, correlation_id=correlation_id
        )

    async def analyze_image(
        self,
        image: bytes,
        *,
        mime_type: str | None = None,
        hint: str | None = None,
        correlation_id: str | None = None,
    ) -> VisionResult:
        """Analyze image contents."""
        config = await self._resolve_config()
        route = config["routing"].get("vision", {"provider_id": "fake", "model": ""})
        provider_id = route["provider_id"]
        model = route["model"]

        if provider_id == "gemini":
            from mesiri.bootstrap.settings import GeminiSettings
            from mesiri_ai.adapters.gemini.adapter import GeminiProvider
            from pydantic import SecretStr

            secret = config["secrets"].get("gemini", {})
            api_key = secret.get("api_key")
            if not api_key:
                raise MesiriError.configuration(
                    "Gemini API Key is not configured for Vision.", code="CONFIG_MISSING"
                )

            settings = GeminiSettings(
                api_key=SecretStr(api_key),
                model=model or self._settings.gemini.model,
                timeout_seconds=self._settings.gemini.timeout_seconds,
                max_retries=self._settings.gemini.max_retries,
            )
            provider = GeminiProvider(settings)
            return await provider.analyze_image(
                image, mime_type=mime_type, hint=hint, correlation_id=correlation_id
            )

        # Fallback/Fake
        from mesiri_ai.fakes import FakeVisionProvider

        provider = FakeVisionProvider(fixtures.VALID_RECEIPT_VISION)
        return await provider.analyze_image(
            image, mime_type=mime_type, hint=hint, correlation_id=correlation_id
        )

    async def translate_to_english(
        self,
        text: str,
        *,
        correlation_id: str | None = None,
    ) -> TranslationResult:
        """Translate text to English."""
        config = await self._resolve_config()
        route = config["routing"].get("translation", {"provider_id": "fake", "model": ""})
        provider_id = route["provider_id"]
        model = route["model"]

        if provider_id == "gemini":
            from mesiri.bootstrap.settings import GeminiSettings
            from mesiri_ai.adapters.gemini.adapter import GeminiProvider
            from pydantic import SecretStr

            secret = config["secrets"].get("gemini", {})
            api_key = secret.get("api_key")
            if not api_key:
                raise MesiriError.configuration(
                    "Gemini API Key is not configured for Translation.", code="CONFIG_MISSING"
                )

            settings = GeminiSettings(
                api_key=SecretStr(api_key),
                model=model or self._settings.gemini.model,
                timeout_seconds=self._settings.gemini.timeout_seconds,
                max_retries=self._settings.gemini.max_retries,
            )
            provider = GeminiProvider(settings)
            return await provider.translate_to_english(text, correlation_id=correlation_id)

        # Fallback/Fake
        from mesiri_ai.fakes import FakeTranslationProvider

        provider = FakeTranslationProvider()
        return await provider.translate_to_english(text, correlation_id=correlation_id)
