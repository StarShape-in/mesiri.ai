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
from ...models import ExtractionResult

try:
    from mesiri.bootstrap.settings import DeepSeekSettings
except Exception:  # pragma: no cover
    DeepSeekSettings = Any  # type: ignore

_EXTRACTION_PROMPT = (
    "You extract structured construction-site data from a worker's message. "
    "Return STRICT JSON only, with keys: "
    '"semantic_type" (one of: expense, equipment_usage, material_update, '
    "labour_update, general_site_update, general_question, unknown), "
    '"fields" (object of extracted values), '
    '"missing_fields" (array of expected-but-absent keys), '
    '"field_confidences" (object mapping each field to 0..1). '
    "Never invent values; if unsure, omit or list under missing_fields."
)


class DeepSeekExtractionProvider:
    provider = "deepseek"

    def __init__(self, settings: DeepSeekSettings) -> None:
        self._s = settings

    async def extract(
        self, text: str, *, semantic_hint: str | None = None, correlation_id: str | None = None
    ) -> ExtractionResult:
        api_key = self._s.api_key.get_secret_value() if self._s.api_key else None

        async def _raw() -> Any:
            async with httpx.AsyncClient(timeout=self._s.timeout_seconds) as client:
                resp = await client.post(
                    f"{self._s.base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": self._s.model,
                        "messages": [
                            {"role": "system", "content": _EXTRACTION_PROMPT},
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
            model=self._s.model,
            latency_ms=latency_ms,
        )
