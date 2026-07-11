"""Coordinate the WhatsApp ingress pipeline for verified webhook payloads."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from ingress.deduplication import DeduplicationStore
from ingress.media_handoff import upload_downloaded_media
from ingress.media_ingestion import DownloadedMedia, MediaDownloader
from ingress.normalization import MessageNormalizer
from mesiri_contracts.assistant import NormalizedMessage
from mesiri_contracts.common.storage import ObjectStoragePort
from runtime.logging_ports import TraceLogger
from runtime.noop_loggers import NoopTraceLogger

logger = logging.getLogger(__name__)


class NormalizedMessageStore(ABC):
    """Persistence boundary for normalized inbound messages."""

    @abstractmethod
    async def save(self, message: NormalizedMessage) -> None:
        """Persist a normalized message for downstream processing."""


class InMemoryNormalizedMessageStore(NormalizedMessageStore):
    """Process-local store used by M2 ingress before async handoff is introduced."""

    def __init__(self) -> None:
        self._messages: dict[str, NormalizedMessage] = {}
        self._lock = asyncio.Lock()

    async def save(self, message: NormalizedMessage) -> None:
        async with self._lock:
            self._messages[message.message_id] = message
            logger.info("Persisted normalized WhatsApp message: %s", message.message_id)

    async def get(self, message_id: str) -> NormalizedMessage | None:
        async with self._lock:
            return self._messages.get(message_id)


@dataclass(frozen=True, slots=True)
class MessageIngressContext:
    """Context extracted from a Meta webhook change value."""

    message: Mapping[str, Any]
    contacts: tuple[Mapping[str, Any], ...]
    phone_number_id: str | None
    display_phone_number: str | None


class WhatsAppReceiver:
    """Orchestrate deduplication, media retrieval, and normalization for ingress."""

    def __init__(
        self,
        *,
        deduplication_store: DeduplicationStore,
        media_downloader: MediaDownloader,
        message_store: NormalizedMessageStore,
        object_storage: ObjectStoragePort,
        normalizer: MessageNormalizer | None = None,
        on_normalized: (
            Callable[[NormalizedMessage, Mapping[str, Any], str | None], Awaitable[None]] | None
        ) = None,
        trace_logger: TraceLogger | None = None,
    ) -> None:
        self._deduplication_store = deduplication_store
        self._media_downloader = media_downloader
        self._message_store = message_store
        self._object_storage = object_storage
        self._normalizer = normalizer or MessageNormalizer()
        # Optional M3 handoff: invoked after a message is normalized+stored.
        # Takes a replayable envelope of the raw Meta payload alongside the
        # normalized message (see _envelope) so it can be persisted for
        # debugging, and replayed later via `replay()` if processing failed.
        self._on_normalized = on_normalized
        # Best-effort: records ingestion-time failures (media download,
        # normalization, or anything the on_normalized callback lets escape)
        # that would otherwise vanish into stdout with no persisted row.
        self._trace_logger: TraceLogger = trace_logger or NoopTraceLogger()
        self._background_tasks: set[asyncio.Task[None]] = set()

    async def handle_payload(self, payload: Mapping[str, Any]) -> int:
        """Schedule ingress work for all messages in a verified webhook payload."""
        scheduled_count = 0

        for context in self._extract_message_contexts(payload):
            if not await self._deduplication_store.try_claim(str(context.message["id"])):
                continue

            task = asyncio.create_task(self._process_message(context))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            scheduled_count += 1

        logger.info("Scheduled %s WhatsApp message(s) for ingress processing", scheduled_count)
        return scheduled_count

    async def wait_until_idle(self) -> None:
        """Wait for in-flight ingress background tasks to complete."""
        if not self._background_tasks:
            return
        await asyncio.gather(*self._background_tasks, return_exceptions=True)

    async def replay(self, envelope: Mapping[str, Any], *, retry_of_id: str) -> str | None:
        """Re-run ingress for a previously captured envelope (see `_envelope`).

        Used by the admin "retry" action on a failed message. Bypasses the
        webhook-time dedup claim (this is an explicit, one-off admin action,
        not inbound traffic that needs deduping against Meta's at-least-once
        delivery) and threads `retry_of_id` through so the write path can
        record the new attempt as a retry of the original, with a dedup key
        that can't collide with it. Returns the new correlation_id, or None
        if the retry itself failed before a message could even be normalized.
        """
        context = MessageIngressContext(
            message=envelope["message"],
            contacts=tuple(envelope.get("contacts") or ()),
            phone_number_id=envelope.get("phone_number_id"),
            display_phone_number=envelope.get("display_phone_number"),
        )
        normalized = await self._process_message(context, retry_of_id=retry_of_id)
        return normalized.correlation_id if normalized is not None else None

    @staticmethod
    def _envelope(context: MessageIngressContext) -> dict[str, Any]:
        """A self-contained, replayable snapshot of one inbound message —
        everything `MessageNormalizer.normalize` needs, so a failed message
        can be replayed later without re-fetching anything from Meta."""
        return {
            "message": dict(context.message),
            "contacts": [dict(c) for c in context.contacts],
            "phone_number_id": context.phone_number_id,
            "display_phone_number": context.display_phone_number,
        }

    async def _process_message(
        self, context: MessageIngressContext, *, retry_of_id: str | None = None
    ) -> NormalizedMessage | None:
        message_id = str(context.message["id"])
        try:
            downloaded_media = await self._download_media_if_required(context.message)
            media = None
            if downloaded_media is not None:
                media = await upload_downloaded_media(
                    message_id=message_id,
                    downloaded=downloaded_media,
                    object_storage=self._object_storage,
                )
            normalized = self._normalizer.normalize(
                context.message,
                contacts=context.contacts,
                phone_number_id=context.phone_number_id,
                display_phone_number=context.display_phone_number,
                media=media,
            )

            await self._message_store.save(normalized)
            if self._on_normalized is not None:
                await self._on_normalized(normalized, self._envelope(context), retry_of_id)
            return normalized
        except Exception as exc:
            logger.exception("Failed to process WhatsApp message %s", message_id)
            # This is the last line of defence: process_inbound_message already
            # persists a trace row for failures in its own stages, so this only
            # fires for failures upstream of it (media download, normalization)
            # or a stage exception that somehow still escaped unlogged.
            try:
                await self._trace_logger.log_stage(
                    correlation_id=f"unrouted:{message_id}",
                    stage="ingress",
                    stage_payload=None,
                    duration_ms=None,
                    succeeded=False,
                    error_code=type(exc).__name__,
                    error_message=str(exc),
                    severity="error",
                    event_source="unhandled_exception",
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Failed to record ingress failure trace for message %s", message_id
                )

    async def _download_media_if_required(
        self,
        message: Mapping[str, Any],
    ) -> DownloadedMedia | None:
        message_type = message.get("type")
        if message_type in ("text", "interactive"):
            return None

        if message_type == "image":
            media_id = (message.get("image") or {}).get("id")
        elif message_type == "audio":
            media_id = (message.get("audio") or {}).get("id")
        else:
            raise ValueError(f"Unsupported WhatsApp message type: {message_type}")

        if not media_id:
            raise ValueError("Media message is missing media id")

        return await self._media_downloader.download(str(media_id))

    def _extract_message_contexts(
        self,
        payload: Mapping[str, Any],
    ) -> Iterator[MessageIngressContext]:
        return _iter_message_contexts(payload)


def _iter_message_contexts(payload: Mapping[str, Any]) -> Iterator[MessageIngressContext]:
    entries = payload.get("entry") or []
    for entry in entries:
        changes = entry.get("changes") or []
        for change in changes:
            if change.get("field") != "messages":
                continue

            value = change.get("value") or {}
            messages = value.get("messages") or []
            contacts = tuple(value.get("contacts") or [])
            metadata = value.get("metadata") or {}
            phone_number_id = metadata.get("phone_number_id")
            display_phone_number = metadata.get("display_phone_number")

            for message in messages:
                yield MessageIngressContext(
                    message=message,
                    contacts=contacts,
                    phone_number_id=str(phone_number_id) if phone_number_id else None,
                    display_phone_number=(
                        str(display_phone_number) if display_phone_number else None
                    ),
                )
