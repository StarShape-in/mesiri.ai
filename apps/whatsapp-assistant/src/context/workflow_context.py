"""Workflow-context and reply-context null providers for M4.

Active workflow context (owned by M5) and reply context binding (owned by M5
Interaction layer) are not yet implemented. M4 represents them behind ports so
the resolver's precedence logic can account for them today. Production wires these
null providers until the respective milestones exist.
"""

from __future__ import annotations


class NullWorkflowContextProvider:
    """Always returns no workflow context (M5 not yet implemented)."""

    async def active_workflow_context(
        self, *, organization_id: str, user_id: str
    ) -> tuple[str | None, str | None] | None:
        return None


class NullReplyContextProvider:
    """Always returns no reply-context binding (M5 Interaction not yet implemented)."""

    async def context_for_reply(
        self, *, organization_id: str, replied_to_message_id: str
    ) -> tuple[str | None, str | None] | None:
        return None
