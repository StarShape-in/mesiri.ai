"""Convert Meta WhatsApp webhook message payloads into NormalizedMessage objects."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from mesiri_contracts.assistant import MediaReference, NormalizedMessage, ReplyContext, SenderInfo
from mesiri_contracts.assistant.enums import InputModality

logger = logging.getLogger(__name__)

_SUPPORTED_TYPES = {
    "text": InputModality.TEXT,
    "image": InputModality.IMAGE,
    "audio": InputModality.VOICE,
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
        media: MediaReference | None = None,
    ) -> NormalizedMessage:
        """Convert one Meta message object into a NormalizedMessage."""
        modality = self._resolve_modality(message)
        sender = self._resolve_sender(message, contacts)
        text = self._resolve_text(message, modality)
        reply_context = self._resolve_reply_context(message)

        normalized = NormalizedMessage(
            message_id=str(message["id"]),
            channel="whatsapp",
            sender=sender,
            timestamp=self._resolve_timestamp(message),
            modality=modality,
            text=text,
            media=media,
            reply_context=reply_context,
            metadata={
                "phone_number_id": phone_number_id,
                "display_phone_number": display_phone_number,
                "raw_type": message.get("type"),
            },
        )
        logger.debug("Normalized WhatsApp message %s as %s", normalized.message_id, modality)
        return normalized

    def _resolve_modality(self, message: Mapping[str, Any]) -> InputModality:
        raw_type = message.get("type")
        if raw_type == "audio":
            audio_payload = message.get("audio") or {}
            if not audio_payload.get("voice"):
                raise ValueError("Unsupported non-voice audio message")
            return InputModality.VOICE

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

    def _resolve_text(
        self,
        message: Mapping[str, Any],
        modality: InputModality,
    ) -> str | None:
        if modality is InputModality.TEXT:
            text_payload = message.get("text") or {}
            return text_payload.get("body")

        if modality is InputModality.IMAGE:
            image_payload = message.get("image") or {}
            return image_payload.get("caption")

        return None

    def _resolve_reply_context(self, message: Mapping[str, Any]) -> ReplyContext | None:
        context = message.get("context") or {}
        reply_to = context.get("message_id")
        if not reply_to:
            return None
        return ReplyContext(replied_to_message_id=str(reply_to))
