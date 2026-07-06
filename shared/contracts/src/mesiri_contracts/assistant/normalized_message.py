"""Canonical normalized message contract consumed by all downstream modules."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.common.ids import new_correlation_id


class SenderInfo(BaseModel):
    """Identity of the WhatsApp user who sent the message."""

    wa_id: str
    phone_number: str | None = None
    profile_name: str | None = None


class MediaReference(BaseModel):
    """Pointer to binary media in object storage — never inline bytes."""

    object_key: str
    mime_type: str | None = None
    size_bytes: int | None = None
    duration_seconds: float | None = None


class ReplyContext(BaseModel):
    """Reply threading metadata for inbound messages."""

    replied_to_message_id: str | None = None
    replied_to_text: str | None = None


class NormalizedMessage(BaseModel):
    """Canonical internal representation of an inbound channel message."""

    message_id: str
    correlation_id: str = Field(default_factory=new_correlation_id)
    channel: str = "whatsapp"
    sender: SenderInfo
    timestamp: datetime
    modality: InputModality
    text: str | None = None
    media: MediaReference | None = None
    reply_context: ReplyContext | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}
