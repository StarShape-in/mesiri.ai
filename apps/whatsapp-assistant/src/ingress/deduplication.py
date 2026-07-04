"""Detect duplicate WhatsApp webhook deliveries using WhatsApp message IDs."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)


class DeduplicationStore(ABC):
    """Persistence boundary for WhatsApp message idempotency keys."""

    @abstractmethod
    async def try_claim(self, message_id: str) -> bool:
        """Return True when the message ID is seen for the first time."""


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
            message_id
            for message_id, seen_at in self._seen.items()
            if seen_at < cutoff
        ]
        for message_id in expired_keys:
            del self._seen[message_id]
