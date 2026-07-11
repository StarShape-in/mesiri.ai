"""DeepSeek structured-extraction adapter (M3).

Implements :class:`StructuredExtractionProvider` against DeepSeek's
OpenAI-compatible chat API (text only, no vision). Uses httpx directly so no
extra SDK is required; responses are parsed into the Mesiri-owned
``ExtractionResult`` and malformed output maps to PROVIDER_MALFORMED_OUTPUT.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from ...core.errors import malformed_output
from ...core.fallback import call_with_resilience
from ...models import ExtractionResult, TranslationResult

try:
    from mesiri.bootstrap.settings import DeepSeekSettings
except Exception:  # pragma: no cover
    DeepSeekSettings = Any  # type: ignore

_EXTRACTION_PROMPT = (
    "You extract structured construction-site data from a worker's message. "
    "Return STRICT JSON only, with keys: "
    '"semantic_type" (one of: expense, equipment_usage, material_update, '
    "labour_update, general_site_update, general_question, inventory_query, unknown), "
    '"fields" (object of extracted values), '
    '"missing_fields" (array of expected-but-absent keys), '
    '"field_confidences" (object mapping each field to 0..1). '
    "Never invent values; if unsure, omit or list under missing_fields. quantity is "
    'always a plain number: strip approximation words like "almost", "about", '
    '"around", "roughly", "nearly" and extract the number stated (e.g. "almost 70 '
    'bags" -> quantity 70).\n\n'
    "Field schema per semantic_type (only include keys you actually found):\n"
    "- expense: amount, currency, vendor, category, description, paid_to, occurred_on\n"
    "- equipment_usage: equipment_name, duration_hours, operator, activity\n"
    "- material_update: material_name, quantity, unit, direction, work_item. "
    'direction MUST be exactly "received" or "used" -- never any other word. '
    'Use "received" when material arrived, was delivered, or was brought to site '
    '(e.g. "50 bags of cement arrived", "cement delivered today"). '
    'Use "used" when material was consumed, used, or applied to work '
    '(e.g. "20 bags of cement used for the foundation"). '
    "work_item is only for used material: the activity or task it was used for "
    '(e.g. "slabing the footing area", "column casting"). Omit work_item entirely '
    "for received material.\n"
    "- labour_update: headcount, trade, hours, contractor\n"
    "- general_site_update: summary, activity, location, weather\n"
    "- general_question: question, topic\n"
    "- inventory_query: material_name (omit material_name if asking about all "
    'materials, e.g. "show inventory"). Use this type for questions about how '
    'much of a material is currently in stock (e.g. "how much cement is left?", '
    '"current stock of steel") or its movement history '
    '(e.g. "show today\'s cement history"). This is a question, never an update.'
)


class DeepSeekExtractionProvider:
    provider = "deepseek"

    def __init__(self, settings: DeepSeekSettings) -> None:
        self._s = settings

    async def extract(
        self, text: str, *, semantic_hint: str | None = None, correlation_id: str | None = None
    ) -> ExtractionResult:
        api_key = self._s.api_key.get_secret_value() if self._s.api_key else None
        system_prompt = _EXTRACTION_PROMPT
        if semantic_hint:
            system_prompt += (
                f'\n\nHint: the user selected the "{semantic_hint}" category just before '
                "sending this message. Prefer that semantic_type unless the text clearly "
                "indicates a different one -- never force it against clear evidence."
            )

        async def _raw() -> Any:
            async with httpx.AsyncClient(timeout=self._s.timeout_seconds) as client:
                resp = await client.post(
                    f"{self._s.base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": self._s.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": text},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0,
                    },
                )
                resp.raise_for_status()
                return resp.json()

        raw, latency_ms = await call_with_resilience(
            _raw,
            provider=self.provider,
            operation="extract",
            timeout_seconds=self._s.timeout_seconds,
            max_retries=self._s.max_retries,
            correlation_id=correlation_id,
        )
        try:
            content = raw["choices"][0]["message"]["content"]
            data = json.loads(content)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise malformed_output("deepseek", str(exc), correlation_id=correlation_id) from exc

        return ExtractionResult(
            semantic_type=data.get("semantic_type", "unknown"),
            fields=data.get("fields", {}) or {},
            missing_fields=list(data.get("missing_fields", []) or []),
            field_confidences={
                k: float(v) for k, v in (data.get("field_confidences", {}) or {}).items()
            },
            provider=self.provider,
            model=self._s.model,
            latency_ms=latency_ms,
        )

    async def translate_to_english(
        self, text: str, *, correlation_id: str | None = None
    ) -> TranslationResult:
        api_key = self._s.api_key.get_secret_value() if self._s.api_key else None
        system_prompt = (
            "Translate the following text to English. "
            "Return STRICT JSON only with keys: "
            '"translated_text" (string) and "detected_language" (ISO-639-1 code or null). '
            "Never add commentary."
        )

        async def _raw() -> Any:
            async with httpx.AsyncClient(timeout=self._s.timeout_seconds) as client:
                resp = await client.post(
                    f"{self._s.base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": self._s.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": text},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0,
                    },
                )
                resp.raise_for_status()
                return resp.json()

        raw, latency_ms = await call_with_resilience(
            _raw,
            provider=self.provider,
            operation="translate",
            timeout_seconds=self._s.timeout_seconds,
            max_retries=self._s.max_retries,
            correlation_id=correlation_id,
        )
        try:
            content = raw["choices"][0]["message"]["content"]
            data = json.loads(content)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise malformed_output("deepseek", str(exc), correlation_id=correlation_id) from exc

        return TranslationResult(
            translated_text=data.get("translated_text", text),
            detected_language=data.get("detected_language"),
            provider=self.provider,
            model=self._s.model,
            latency_ms=latency_ms,
        )
