"""Gemini vision + structured-extraction adapter (M3).

Implements :class:`VisionUnderstandingProvider` and
:class:`StructuredExtractionProvider`. The ``google-genai`` SDK is imported
lazily and isolated here; responses are parsed into Mesiri-owned models, and a
non-JSON / unparseable response is mapped to PROVIDER_MALFORMED_OUTPUT.

NOTE: exact SDK call/field names are assumed and must be verified against the
installed ``google-genai`` version (tracked in the integration report). Tests
use the fake provider.
"""

from __future__ import annotations

import json
from typing import Any

from ...core.errors import malformed_output
from ...core.fallback import call_with_resilience
from ...models import ExtractionResult, SpeechResult, TranslationResult, VisionResult

try:
    from mesiri.bootstrap.settings import GeminiSettings
except Exception:  # pragma: no cover
    GeminiSettings = Any  # type: ignore

_VISION_PROMPT = (
    "You are analysing a construction-site image. Return strict JSON with keys: "
    '"document_classification" (e.g. receipt, invoice, site_photo, unknown), '
    '"description" (short), and "fields" (object of any legible key/values). '
    "Never invent values; omit unknown keys."
)

_EXTRACTION_PROMPT = (
    "Extract structured construction data from the text. Return strict JSON with "
    'keys: "semantic_type" (expense|equipment_usage|material_update|labour_update|'
    "general_site_update|general_question|whoami_question|inventory_query|unknown), "
    '"fields" (object), "missing_fields" (array), '
    '"field_confidences" (object of field->0..1). '
    "Never invent values. quantity is always a plain number: strip approximation "
    'words like "almost", "about", "around", "roughly", "nearly" and extract the '
    'number stated (e.g. "almost 70 bags" -> quantity 70).\n\n'
    "Field schema per semantic_type (only include keys you actually found):\n"
    "Note: For ALL semantic types, if the text mentions a specific project, site, or location by name (e.g. 'project alpha', 'at the main site'), extract it as 'project_name'.\n"
    "- expense: amount, currency, vendor, category, description, paid_to, occurred_on, project_name\n"
    "- equipment_usage: equipment_name, duration_hours, operator, activity, project_name\n"
    "- material_update: material_name, quantity, unit, direction, work_item, project_name. "
    'direction MUST be exactly "received" or "used" -- never any other word. '
    'Use "received" when material arrived, was delivered, or was brought to site '
    '(e.g. "50 bags of cement arrived", "cement delivered today"). '
    'Use "used" when material was consumed, used, or applied to work '
    '(e.g. "20 bags of cement used for the foundation"). '
    'If no direction is explicitly stated (e.g. "record 50 bags of cement"), default to "used". '
    "work_item is only for used material: the activity or task it was used for "
    '(e.g. "slabing the footing area", "column casting"). Omit work_item entirely '
    "for received material.\n"
    "- labour_update: headcount, trade, hours, contractor, project_name\n"
    "- general_site_update: summary, activity, location, weather, project_name\n"
    "- general_question: question, topic\n"
    "- whoami_question: question\n"
    "- inventory_query: material_name (omit material_name if asking about all "
    'materials, e.g. "show inventory"). Use this type for questions about how '
    'much of a material is currently in stock (e.g. "how much cement is left?", '
    '"current stock of steel") or its movement history '
    '(e.g. "show today\'s cement history"). This is a question, never an update.'
)


_TRANSLATION_PROMPT = (
    "Translate the following text to English. Also identify the source language if possible. "
    'Return strict JSON with keys: "translated_text" and "detected_language". '
    "If it is already English, just return the text as translated_text and 'English' as detected_language."
)


class GeminiProvider:
    provider = "gemini"

    def __init__(self, settings: GeminiSettings) -> None:
        self._settings = settings
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai  # lazy: only the gemini lane needs it

            api_key = self._settings.api_key.get_secret_value() if self._settings.api_key else None
            self._client = genai.Client(api_key=api_key)
        return self._client

    async def _generate(
        self, contents: Any, correlation_id: str | None, operation: str
    ) -> tuple[str, float]:
        client = self._get_client()

        async def _raw() -> Any:
            import asyncio

            def _call() -> Any:
                return client.models.generate_content(
                    model=self._settings.model,
                    contents=contents,
                )

            return await asyncio.to_thread(_call)

        resp, latency_ms = await call_with_resilience(
            _raw,
            provider=self.provider,
            operation=operation,
            timeout_seconds=self._settings.timeout_seconds,
            max_retries=self._settings.max_retries,
            correlation_id=correlation_id,
        )
        text = getattr(resp, "text", None) or ""
        return text, latency_ms

    @staticmethod
    def _parse_json(text: str, correlation_id: str | None) -> dict[str, Any]:
        cleaned = (
            text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        )
        try:
            data = json.loads(cleaned)
        except (ValueError, TypeError) as exc:
            raise malformed_output("gemini", str(exc), correlation_id=correlation_id) from exc
        if not isinstance(data, dict):
            raise malformed_output(
                "gemini", "top-level JSON is not an object", correlation_id=correlation_id
            )
        return data

    async def analyze_image(
        self,
        image: bytes,
        *,
        mime_type: str | None = None,
        hint: str | None = None,
        correlation_id: str | None = None,
    ) -> VisionResult:
        from google.genai import types  # lazy

        part = types.Part.from_bytes(data=image, mime_type=mime_type or "image/jpeg")
        text, latency_ms = await self._generate(
            [_VISION_PROMPT, part], correlation_id, "analyze_image"
        )
        data = self._parse_json(text, correlation_id)
        return VisionResult(
            document_classification=data.get("document_classification"),
            description=data.get("description"),
            raw_fields=data.get("fields", {}) or {},
            provider=self.provider,
            model=self._settings.model,
            latency_ms=latency_ms,
        )

    async def extract(
        self, text: str, *, semantic_hint: str | None = None, correlation_id: str | None = None
    ) -> ExtractionResult:
        prompt = f"{_EXTRACTION_PROMPT}\n\nText:\n{text}"
        if semantic_hint:
            prompt += (
                f'\n\nHint: the user selected the "{semantic_hint}" category just before '
                "sending this message. Prefer that semantic_type unless the text clearly "
                "indicates a different one -- never force it against clear evidence."
            )
        raw_text, latency_ms = await self._generate(prompt, correlation_id, "extract")
        data = self._parse_json(raw_text, correlation_id)
        return ExtractionResult(
            semantic_type=data.get("semantic_type", "unknown"),
            fields=data.get("fields", {}) or {},
            missing_fields=list(data.get("missing_fields", []) or []),
            field_confidences={
                k: float(v) for k, v in (data.get("field_confidences", {}) or {}).items()
            },
            provider=self.provider,
            model=self._settings.model,
            latency_ms=latency_ms,
        )

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        correlation_id: str | None = None,
    ) -> str:
        prompt = f"{system_prompt}\n\n{user_prompt}"
        raw_text, _latency_ms = await self._generate(prompt, correlation_id, "generate_json")
        return (
            raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        )

    async def translate_to_english(
        self, text: str, *, correlation_id: str | None = None
    ) -> TranslationResult:
        prompt = f"{_TRANSLATION_PROMPT}\n\nText:\n{text}"
        raw_text, latency_ms = await self._generate(prompt, correlation_id, "translate")
        data = self._parse_json(raw_text, correlation_id)
        return TranslationResult(
            translated_text=data.get("translated_text", text),
            detected_language=data.get("detected_language"),
            provider=self.provider,
            model=self._settings.model,
            latency_ms=latency_ms,
        )

    async def transcribe(
        self,
        audio: bytes,
        *,
        language_hint: str | None = None,
        correlation_id: str | None = None,
    ) -> SpeechResult:
        from google.genai import types  # lazy

        part = types.Part.from_bytes(data=audio, mime_type="audio/ogg")
        prompt = "Transcribe the audio accurately. Output the transcript directly without any prefix or commentary."
        text, latency_ms = await self._generate([prompt, part], correlation_id, "transcribe")
        return SpeechResult(
            transcript=text.strip(),
            detected_language=None,
            translated_text=text.strip(),
            provider=self.provider,
            model=self._settings.model,
            latency_ms=latency_ms,
        )
