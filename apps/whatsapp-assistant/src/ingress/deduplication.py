"""Detect duplicate WhatsApp webhook deliveries using WhatsApp message IDs."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Protocol

logger = logging.getLogger(__name__)


class DeduplicationStore(ABC):
    """Persistence boundary for WhatsApp message idempotency keys."""

    @abstractmethod
    async def try_claim(self, message_id: str) -> bool:
        """Return True when the message ID is seen for the first time."""


class _RedisLike(Protocol):
    """The one Redis capability dedup needs: an atomic, TTL'd claim.

    Mirrors the narrow-protocol convention used by context/active_context.py
    and interactions/pending_media.py rather than importing RedisClient --
    the assistant depends on capabilities, not on the backend's adapter.
    """

    async def set_if_absent(
        self, key: str, value: str, *, ttl_seconds: int | None = None
    ) -> bool: ...


class RedisDeduplicationStore(DeduplicationStore):
    """Cross-process, restart-surviving deduplication.

    InMemoryDeduplicationStore below loses every claim on restart, which
    reopens the full 24-hour window: Meta re-delivers unacknowledged messages,
    so a deploy in the middle of a burst could re-run journeys that already
    wrote business records. It is also process-local, so it cannot dedup at
    all once more than one worker is running.

    The claim is SET NX with a TTL, so it is atomic across processes and
    self-expiring -- there is no cleanup path and no unbounded key growth.
    A Redis failure fails OPEN (returns True, message is processed): dropping
    a real message is strictly worse than the rare double-process that
    downstream idempotency keys already defend against.
    """

    def __init__(self, redis: _RedisLike, *, ttl: timedelta = timedelta(hours=24)) -> None:
        self._redis = redis
        self._ttl_seconds = int(ttl.total_seconds())

    @staticmethod
    def _key(message_id: str) -> str:
        return f"dedup:message:{message_id}"

    async def try_claim(self, message_id: str) -> bool:
        try:
            claimed = await self._redis.set_if_absent(
                self._key(message_id), "1", ttl_seconds=self._ttl_seconds
            )
        except Exception:  # noqa: BLE001 -- fail open, see class docstring
            logger.exception(
                "dedup.redis_unavailable message_id=%s -- processing anyway", message_id
            )
            return True
        if not claimed:
            logger.info("Duplicate WhatsApp message ignored: %s", message_id)
        return claimed


class InMemoryDeduplicationStore(DeduplicationStore):
    """Process-local deduplication store suitable for single-instance M2 ingress."""

    def __init__(self, *, ttl: timedelta = timedelta(hours=24)) -> None:
        self._ttl = ttl
        self._seen: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def try_claim(self, message_id: str) -> bool:
        async with self._lock:
            self._evict_expired()
            if message_id in self._seen:
                logger.info("Duplicate WhatsApp message ignored: %s", message_id)
                return False

            self._seen[message_id] = datetime.now(tz=UTC)
            logger.debug("Claimed WhatsApp message idempotency key: %s", message_id)
            return True

    def _evict_expired(self) -> None:
        cutoff = datetime.now(tz=UTC) - self._ttl
        expired_keys = [
            message_id for message_id, seen_at in self._seen.items() if seen_at < cutoff
        ]
        for message_id in expired_keys:
            del self._seen[message_id]
