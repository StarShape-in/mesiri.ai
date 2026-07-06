"""Fake read-only scope adapter for Context resolver tests."""

from __future__ import annotations

from mesiri_contracts.common.errors import MesiriError
from mesiri_contracts.context.ports import ScopeRecord


class FakeScopeLookupPort:
    """In-memory project/site scope lookup for tests."""

    def __init__(
        self,
        *,
        default_scopes: dict[tuple[str, str], ScopeRecord | None] | None = None,
        reply_scopes: dict[str, ScopeRecord | None] | None = None,
        fail_with: MesiriError | None = None,
    ) -> None:
        self._default_scopes = default_scopes or {}
        self._reply_scopes = reply_scopes or {}
        self.fail_with = fail_with

    def set_default_scope(
        self,
        user_id: str,
        organization_id: str,
        record: ScopeRecord | None,
    ) -> None:
        self._default_scopes[(user_id, organization_id)] = record

    def set_reply_scope(self, replied_to_message_id: str, record: ScopeRecord | None) -> None:
        self._reply_scopes[replied_to_message_id] = record

    async def resolve_default_scope(
        self,
        user_id: str,
        organization_id: str,
        *,
        correlation_id: str,
    ) -> ScopeRecord | None:
        if self.fail_with is not None:
            raise self.fail_with
        return self._default_scopes.get((user_id, organization_id))

    async def resolve_by_reply(
        self,
        replied_to_message_id: str,
        *,
        correlation_id: str,
    ) -> ScopeRecord | None:
        if self.fail_with is not None:
            raise self.fail_with
        return self._reply_scopes.get(replied_to_message_id)
