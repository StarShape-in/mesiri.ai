"""Guard against a misconfigured object-storage adapter leaking into responses.

The local/test fake adapter (`FakeObjectStorage`) returns `memory://...`
links instead of real downloadable URLs -- fine in-process, but if it is
ever selected in a production-like deployment (e.g. the provider env var
was never set), every attachment/photo URL silently becomes unusable and
the only visible symptom is a browser console `ERR_UNKNOWN_URL_SCHEME` on
an otherwise-normal-looking API response. `Settings.validate_runtime()` is
meant to refuse to boot in that situation, but this is a second, independent
check at the point the URL actually leaves the backend -- so a gap in that
guard surfaces as a clear 500 with a diagnosable message, not a silently
broken image.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def assert_downloadable_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        logger.error(
            "object storage returned a non-downloadable URL scheme (%r) -- "
            "the configured provider cannot be used outside local/test",
            url.split(":", 1)[0],
        )
        raise HTTPException(
            status_code=500,
            detail="Media storage is not configured for this environment.",
        )
    return url
