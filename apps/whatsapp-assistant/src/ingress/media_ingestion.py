"""Download WhatsApp media assets from the Meta Cloud API."""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


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

        metadata_response = await self._client.get(
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

        media_response = await self._client.get(
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
