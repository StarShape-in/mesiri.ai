"""Canonical normalized message contract consumed by all downstream modules."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from mesiri_contracts.common.ids import new_correlation_id


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
    # Object-storage key once the media is placed behind the ObjectStorage
    # boundary (set by the M2->M3 media handoff). Downstream reads media via the
    # ObjectStoragePort using this key, never the local file_path directly.
    object_key: str | None = None
    sha256: str | None = None
    file_size: int | None = None


class NormalizedMessage(BaseModel):
    """Canonical internal representation of an inbound channel message."""

    message_id: str
    # One correlation id per user journey, minted at ingress and propagated
    # end-to-end (transport -> understanding -> ...). Added for INT-001 so M3 can
    # keep the whole journey traceable; defaults so existing producers stay valid.
    correlation_id: str = Field(default_factory=new_correlation_id)
    channel: str = "whatsapp"
    sender: SenderInfo
    timestamp: datetime
    message_type: MessageType
    content: str | None = None
    media: MediaInfo | None = None
    reply_to: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
