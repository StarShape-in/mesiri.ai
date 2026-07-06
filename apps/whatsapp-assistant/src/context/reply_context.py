"""Reply-context provider (M4).

Maps a replied-to WhatsApp message id to the (project_id, site_id) it was
resolved under. The authoritative mapping is owned by the conversation/message
store (persisted when a message is answered). Until that store exists, M4 wires
a ``NullReplyContextProvider`` in production and a ``FakeReplyContextProvider``
(see ``fakes``) in tests — both satisfy ``ReplyContextProvider``.
"""

from __future__ import annotations


class NullReplyContextProvider:
    """Always returns no reply context (safe default before the store exists)."""

    async def context_for_reply(
        self, *, organization_id: str, replied_to_message_id: str
    ) -> tuple[str | None, str | None] | None:
        return None
