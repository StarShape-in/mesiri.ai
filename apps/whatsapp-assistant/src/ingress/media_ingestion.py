"""Download WhatsApp media assets from the Meta Cloud API."""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DownloadedMedia:
    """Local representation of media retrieved from Meta."""

    media_id: str
    mime_type: str | None
    file_path: str
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
        download_dir: Path,
        graph_base_url: str = "https://graph.facebook.com",
    ) -> None:
        self._client = client
        self._access_token = access_token
        self._api_version = api_version
        self._download_dir = download_dir
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

        self._download_dir.mkdir(parents=True, exist_ok=True)
        extension = _extension_for_mime_type(mime_type)
        file_path = self._download_dir / f"{media_id}-{uuid4().hex}{extension}"
        file_path.write_bytes(content)

        computed_sha256 = hashlib.sha256(content).hexdigest()
        if sha256 and sha256 != computed_sha256:
            logger.warning(
                "SHA256 mismatch for media %s: meta=%s computed=%s",
                media_id,
                sha256,
                computed_sha256,
            )

        logger.info(
            "Downloaded WhatsApp media %s to %s (%s bytes)",
            media_id,
            file_path,
            len(content),
        )

        return DownloadedMedia(
            media_id=media_id,
            mime_type=mime_type,
            file_path=str(file_path),
            sha256=sha256 or computed_sha256,
            file_size=len(content),
        )


def _extension_for_mime_type(mime_type: str | None) -> str:
    if not mime_type:
        return ".bin"

    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "audio/ogg": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
    }

    for prefix, extension in mapping.items():
        if mime_type.startswith(prefix):
            return extension

    return ".bin"
