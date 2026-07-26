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
    """Upload the already-in-memory media bytes and return the shared media
    reference for M3. No local disk round trip -- `downloaded.content` came
    straight off the Meta CDN response; the old code path wrote it to a temp
    file here and read it back, a synchronous disk write + read blocking the
    event loop on every image/voice message for no consumer that ever needed
    the file to exist on disk (see media_ingestion.py's DownloadedMedia)."""
    object_key = f"media/{message_id}/{downloaded.media_id}"
    await object_storage.put_object(
        object_key, downloaded.content, content_type=downloaded.mime_type
    )
    return MediaReference(
        object_key=object_key,
        mime_type=downloaded.mime_type,
        size_bytes=downloaded.file_size,
    )
