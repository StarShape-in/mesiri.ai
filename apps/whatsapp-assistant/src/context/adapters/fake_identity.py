"""Fake read-only identity adapter for Context resolver tests."""

from __future__ import annotations

from mesiri_contracts.common.errors import MesiriError
from mesiri_contracts.context.ports import IdentityRecord


class FakeIdentityLookupPort:
    """In-memory identity lookup keyed by WhatsApp ``wa_id``."""

    def __init__(
        self,
        identities: dict[str, IdentityRecord] | None = None,
        *,
        fail_with: MesiriError | None = None,
    ) -> None:
        self._identities = identities or {}
        self.fail_with = fail_with

    def register(self, record: IdentityRecord) -> None:
        self._identities[record.whatsapp_wa_id] = record

    async def resolve_by_whatsapp(
        self,
        wa_id: str,
        *,
        correlation_id: str,
    ) -> IdentityRecord | None:
        if self.fail_with is not None:
            raise self.fail_with
        return self._identities.get(wa_id)
