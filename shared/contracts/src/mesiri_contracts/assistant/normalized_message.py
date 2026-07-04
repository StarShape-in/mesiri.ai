"""Canonical normalized message contract consumed by all downstream modules."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Supported inbound WhatsApp message categories for M2 ingress."""

    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"


class SenderInfo(BaseModel):
    """Identity of the WhatsApp user who sent the message."""

    wa_id: str
    phone_number: str | None = None
    profile_name: str | None = None


class MediaInfo(BaseModel):
    """Downloaded media metadata attached to a normalized message."""

    media_id: str
    mime_type: str | None = None
    file_path: str | None = None
    sha256: str | None = None
    file_size: int | None = None


class NormalizedMessage(BaseModel):
    """Canonical internal representation of an inbound channel message."""

    message_id: str
    channel: str = "whatsapp"
    sender: SenderInfo
    timestamp: datetime
    message_type: MessageType
    content: str | None = None
    media: MediaInfo | None = None
    reply_to: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
