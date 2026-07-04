"""M3-side reading model for NormalizedMessage (M2 → M3 boundary).

IMPORTANT — this is NOT the authoritative contract. ``NormalizedMessage.v1`` is
owned by Alan (M2) and its code lives in ``mesiri_contracts.assistant``. That
file is still empty at the time of writing (M0 defined the shape in docs only),
so M3 defines this *consumer-side reading model* to build fixtures and the
integration harness against the documented shape.

It is deliberately lenient (``extra="ignore"``) so M3 accepts any schema-valid
NormalizedMessage the real M2 produces, including additive fields — honouring
"Ilan guarantees acceptance of every valid NormalizedMessage fixture".

When Alan authors the authoritative contract, this reading model should be
replaced by importing it directly. See ``docs/execution/M2_M3_INTEGRATION_GAP.md``.
"""

from __future__ import annotations

from pydantic import BaseModel

from mesiri_contracts.assistant.enums import InputModality


class MediaReference(BaseModel):
    """Pointer to binary media in object storage — never inline bytes."""

    object_key: str
    mime_type: str | None = None
    size_bytes: int | None = None
    duration_seconds: float | None = None

    model_config = {"extra": "ignore"}


class ReplyContext(BaseModel):
    replied_to_message_id: str | None = None
    replied_to_text: str | None = None

    model_config = {"extra": "ignore"}


class InteractiveResponse(BaseModel):
    reply_id: str | None = None
    title: str | None = None

    model_config = {"extra": "ignore"}


class NormalizedMessageRef(BaseModel):
    """Consumer-side view of an M2 NormalizedMessage."""

    message_id: str
    external_message_id: str | None = None
    correlation_id: str
    causation_id: str | None = None
    timestamp: str | None = None

    modality: InputModality
    text: str | None = None
    media: MediaReference | None = None
    reply_context: ReplyContext | None = None
    interactive_response: InteractiveResponse | None = None

    # Accept (and ignore) any additive fields the real contract carries.
    model_config = {"extra": "ignore"}
