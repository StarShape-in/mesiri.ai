"""Place downloaded WhatsApp media behind the object-storage boundary (M2)."""

from __future__ import annotations

from ingress.media_ingestion import DownloadedMedia
from mesiri_contracts.assistant import MediaReference
from mesiri_contracts.common.storage import ObjectStoragePort


async def upload_downloaded_media(
    *,
    message_id: str,
    downloaded: DownloadedMedia,
    object_storage: ObjectStoragePort,
) -> MediaReference:
    """Upload local media bytes and return the shared media reference for M3."""
    object_key = f"media/{message_id}/{downloaded.media_id}"
    with open(downloaded.file_path, "rb") as file_handle:
        data = file_handle.read()
    await object_storage.put_object(object_key, data, content_type=downloaded.mime_type)
    return MediaReference(
        object_key=object_key,
        mime_type=downloaded.mime_type,
        size_bytes=downloaded.file_size,
    )
