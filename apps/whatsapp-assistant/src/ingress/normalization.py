"""Convert Meta WhatsApp webhook message payloads into NormalizedMessage objects."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

from mesiri_contracts.assistant import MediaInfo, MessageType, NormalizedMessage, SenderInfo

from ingress.media_ingestion import DownloadedMedia

logger = logging.getLogger(__name__)

_SUPPORTED_TYPES = {
    "text": MessageType.TEXT,
    "image": MessageType.IMAGE,
    "audio": MessageType.VOICE,
}


class MessageNormalizer:
    """Map Meta webhook message payloads to Mesiri's canonical message format."""

    def normalize(
        self,
        message: Mapping[str, Any],
        *,
        contacts: Sequence[Mapping[str, Any]],
        phone_number_id: str | None,
        display_phone_number: str | None,
        downloaded_media: DownloadedMedia | None = None,
    ) -> NormalizedMessage:
        """Convert one Meta message object into a NormalizedMessage."""
        message_type = self._resolve_message_type(message)
        sender = self._resolve_sender(message, contacts)
        content = self._resolve_content(message, message_type)
        media = self._resolve_media(message, message_type, downloaded_media)
        reply_to = self._resolve_reply_to(message)

        normalized = NormalizedMessage(
            message_id=str(message["id"]),
            channel="whatsapp",
            sender=sender,
            timestamp=self._resolve_timestamp(message),
            message_type=message_type,
            content=content,
            media=media,
            reply_to=reply_to,
            metadata={
                "phone_number_id": phone_number_id,
                "display_phone_number": display_phone_number,
                "raw_type": message.get("type"),
            },
        )
        logger.debug("Normalized WhatsApp message %s as %s", normalized.message_id, message_type)
        return normalized

    def _resolve_message_type(self, message: Mapping[str, Any]) -> MessageType:
        raw_type = message.get("type")
        if raw_type == "audio":
            audio_payload = message.get("audio") or {}
            if not audio_payload.get("voice"):
                raise ValueError("Unsupported non-voice audio message")
            return MessageType.VOICE

        resolved = _SUPPORTED_TYPES.get(raw_type)
        if resolved is None:
            raise ValueError(f"Unsupported WhatsApp message type: {raw_type}")

        return resolved

    def _resolve_sender(
        self,
        message: Mapping[str, Any],
        contacts: Sequence[Mapping[str, Any]],
    ) -> SenderInfo:
        wa_id = str(message["from"])
        profile_name = None

        for contact in contacts:
            if str(contact.get("wa_id")) == wa_id:
                profile = contact.get("profile") or {}
                profile_name = profile.get("name")
                break

        return SenderInfo(
            wa_id=wa_id,
            phone_number=wa_id,
            profile_name=profile_name,
        )

    def _resolve_timestamp(self, message: Mapping[str, Any]) -> datetime:
        timestamp = int(message["timestamp"])
        return datetime.fromtimestamp(timestamp, tz=UTC)

    def _resolve_content(
        self,
        message: Mapping[str, Any],
        message_type: MessageType,
    ) -> str | None:
        if message_type is MessageType.TEXT:
            text_payload = message.get("text") or {}
            return text_payload.get("body")

        if message_type is MessageType.IMAGE:
            image_payload = message.get("image") or {}
            return image_payload.get("caption")

        return None

    def _resolve_media(
        self,
        message: Mapping[str, Any],
        message_type: MessageType,
        downloaded_media: DownloadedMedia | None,
    ) -> MediaInfo | None:
        if message_type not in {MessageType.IMAGE, MessageType.VOICE}:
            return None

        payload_key = "image" if message_type is MessageType.IMAGE else "audio"
        media_payload = message.get(payload_key) or {}
        media_id = media_payload.get("id")
        if not media_id:
            raise ValueError(f"Missing media id for {message_type.value} message")

        if downloaded_media is None:
            raise ValueError(
                f"Downloaded media is required for {message_type.value} messages"
            )

        if downloaded_media.media_id != media_id:
            raise ValueError("Downloaded media id does not match webhook payload")

        return MediaInfo(
            media_id=media_id,
            mime_type=downloaded_media.mime_type or media_payload.get("mime_type"),
            file_path=downloaded_media.file_path,
            sha256=downloaded_media.sha256 or media_payload.get("sha256"),
            file_size=downloaded_media.file_size,
        )

    def _resolve_reply_to(self, message: Mapping[str, Any]) -> str | None:
        context = message.get("context") or {}
        reply_to = context.get("message_id")
        return str(reply_to) if reply_to else None
