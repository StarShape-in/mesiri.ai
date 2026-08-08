"""Download WhatsApp media assets from the Meta Cloud API."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Statuses worth a second try -- rate limiting and infra hiccups, not "this
# will never work" errors like 4xx auth/not-found.
_TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
# Short and bounded on purpose: this runs inline in front of a user waiting
# for a reply (see ingress/receiver.py's _process_message_locked), so it
# must absorb a brief blip without turning a real outage into a long hang.
# Two retries, sub-second backoff -- worst case adds ~1.2s only when the
# first attempt actually fails; zero added latency on the (overwhelmingly
# common) success path.
_RETRY_DELAYS_SECONDS = (0.3, 0.9)


async def _get_with_retry(client: httpx.AsyncClient, url: str, **kwargs: object) -> httpx.Response:
    """GET with a couple of short retries on transient failures only.

    Without this, a single dropped connection or transient 503 from Meta's
    CDN/Graph API permanently loses the message: the exception propagates up
    through _process_message_locked, which logs it and returns without
    re-raising (see docs/... rationale in that method), so nothing further
    ever retries the download on its own. This absorbs the common transient
    case before it ever gets that far. A non-transient failure (4xx, DNS
    failure after retries) still raises immediately/eventually -- ARQ's own
    max_tries (worker.py) is the next line of defence for anything this
    doesn't catch.
    """
    last_exc: Exception | None = None
    for attempt, delay in enumerate((0.0, *_RETRY_DELAYS_SECONDS)):
        if delay:
            logger.warning(
                "Retrying WhatsApp media fetch after transient failure (attempt %d): %s",
                attempt,
                url,
            )
            await asyncio.sleep(delay)
        try:
            response = await client.get(url, **kwargs)  # type: ignore[arg-type]
        except httpx.TransportError as exc:
            last_exc = exc
            continue
        if response.status_code in _TRANSIENT_STATUS_CODES:
            last_exc = httpx.HTTPStatusError(
                f"transient status {response.status_code} from {url}",
                request=response.request,
                response=response,
            )
            continue
        return response
    assert last_exc is not None  # loop always returns or sets this before exiting
    raise last_exc


@dataclass(frozen=True, slots=True)
class DownloadedMedia:
    """In-memory representation of media retrieved from Meta.

    Carries the bytes directly (``content``) rather than a path to a
    temp-directory copy -- the old shape wrote every download to disk and had
    media_handoff.py immediately read it back before uploading to object
    storage, which is a synchronous disk write + read on the event loop for
    every image/voice message, for a file nothing else ever consumed (see the
    latency report's ~10-16s of untraced "ingress" time on images)."""

    media_id: str
    mime_type: str | None
    content: bytes
    sha256: str | None
    file_size: int


class MediaDownloader(ABC):
    """Abstraction for retrieving WhatsApp media referenced by webhook payloads."""

    @abstractmethod
    async def download(self, media_id: str) -> DownloadedMedia:
        """Download media content and return local file metadata."""


class MetaMediaDownloader(MediaDownloader):
    """Download WhatsApp media using the Meta Graph API."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        access_token: str,
        api_version: str,
        graph_base_url: str = "https://graph.facebook.com",
    ) -> None:
        self._client = client
        self._access_token = access_token
        self._api_version = api_version
        self._graph_base_url = graph_base_url.rstrip("/")

    async def download(self, media_id: str) -> DownloadedMedia:
        metadata_url = f"{self._graph_base_url}/{self._api_version}/{media_id}"
        logger.info("Fetching WhatsApp media metadata: %s", media_id)

        metadata_response = await _get_with_retry(
            self._client,
            metadata_url,
            params={"access_token": self._access_token},
        )
        metadata_response.raise_for_status()
        metadata = metadata_response.json()

        download_url = metadata.get("url")
        if not download_url:
            raise ValueError(f"Meta media metadata for {media_id} did not include a URL")

        mime_type = metadata.get("mime_type")
        sha256 = metadata.get("sha256")

        media_response = await _get_with_retry(
            self._client,
            download_url,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        media_response.raise_for_status()
        content = media_response.content

        computed_sha256 = hashlib.sha256(content).hexdigest()
        if sha256 and sha256 != computed_sha256:
            logger.warning(
                "SHA256 mismatch for media %s: meta=%s computed=%s",
                media_id,
                sha256,
                computed_sha256,
            )

        logger.info(
            "Downloaded WhatsApp media %s (%s bytes)",
            media_id,
            len(content),
        )

        return DownloadedMedia(
            media_id=media_id,
            mime_type=mime_type,
            content=content,
            sha256=sha256 or computed_sha256,
            file_size=len(content),
        )
