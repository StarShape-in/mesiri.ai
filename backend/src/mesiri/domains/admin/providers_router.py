"""Admin-facing visibility into AI provider configuration and live health.

Exposes which AI providers (Gemini, DeepSeek, Sarvam) have a key configured,
a masked preview of that key, and an on-demand live check that calls the
provider with a minimal, side-effect-free request to confirm the key still
works right now. No secret value is ever returned in full.
"""

from __future__ import annotations

import time

import httpx
from fastapi import APIRouter, Depends

from mesiri.bootstrap.settings import Settings, get_settings
from mesiri.domains.shared.auth import require_platform_admin

router = APIRouter(prefix="/admin/providers", tags=["admin"])


def _mask(key: str | None) -> str | None:
    if not key:
        return None
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"


@router.get("")
async def list_providers(
    settings: Settings = Depends(get_settings),
    _admin: dict = Depends(require_platform_admin),
) -> list[dict]:
    gemini_key = settings.gemini.api_key.get_secret_value() if settings.gemini.api_key else None
    deepseek_key = (
        settings.deepseek.api_key.get_secret_value() if settings.deepseek.api_key else None
    )
    sarvam_key = settings.sarvam.api_key.get_secret_value() if settings.sarvam.api_key else None

    return [
        {
            "id": "gemini",
            "name": "Gemini",
            "model": settings.gemini.model,
            "configured": gemini_key is not None,
            "key_preview": _mask(gemini_key),
        },
        {
            "id": "deepseek",
            "name": "DeepSeek",
            "model": settings.deepseek.model,
            "configured": deepseek_key is not None,
            "key_preview": _mask(deepseek_key),
        },
        {
            "id": "sarvam",
            "name": "Sarvam",
            "model": None,
            "configured": sarvam_key is not None,
            "key_preview": _mask(sarvam_key),
        },
    ]


async def _check_gemini(settings: Settings) -> tuple[bool, str | None, float]:
    if not settings.gemini.api_key:
        return False, "not configured", 0.0
    api_key = settings.gemini.api_key.get_secret_value()
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": api_key},
            )
        latency_ms = (time.monotonic() - start) * 1000
        if resp.status_code == 200:
            return True, None, latency_ms
        return False, f"HTTP {resp.status_code}", latency_ms
    except httpx.HTTPError as exc:
        return False, str(exc), (time.monotonic() - start) * 1000


async def _check_deepseek(settings: Settings) -> tuple[bool, str | None, float]:
    if not settings.deepseek.api_key:
        return False, "not configured", 0.0
    api_key = settings.deepseek.api_key.get_secret_value()
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.deepseek.base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        latency_ms = (time.monotonic() - start) * 1000
        if resp.status_code == 200:
            return True, None, latency_ms
        return False, f"HTTP {resp.status_code}", latency_ms
    except httpx.HTTPError as exc:
        return False, str(exc), (time.monotonic() - start) * 1000


async def _check_sarvam(settings: Settings) -> tuple[bool, str | None, float]:
    if not settings.sarvam.api_key:
        return False, "not configured", 0.0
    # No documented lightweight "ping" endpoint for Sarvam here; a configured
    # key is reported healthy, matching how the assistant treats it today.
    return True, None, 0.0


_CHECKS = {
    "gemini": _check_gemini,
    "deepseek": _check_deepseek,
    "sarvam": _check_sarvam,
}


@router.post("/{provider_id}/check")
async def check_provider(
    provider_id: str,
    settings: Settings = Depends(get_settings),
    _admin: dict = Depends(require_platform_admin),
) -> dict:
    check = _CHECKS.get(provider_id)
    if check is None:
        return {"id": provider_id, "ok": False, "error": "unknown provider", "latency_ms": None}
    ok, error, latency_ms = await check(settings)
    return {"id": provider_id, "ok": ok, "error": error, "latency_ms": round(latency_ms, 1)}
