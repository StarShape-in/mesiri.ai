"""Workflow-context provider port binding (M4).

Active workflow context (e.g. a running missing-field loop that already knows the
project) is owned by the M5 Workflow Runtime, which M4 does not implement. M4
represents it behind ``WorkflowContextProvider`` (see ``ports``) so precedence
can account for it today. Production wires the ``NullWorkflowContextProvider``
until M5 exists; tests use ``FakeWorkflowContextProvider``.
"""

from __future__ import annotations


class NullWorkflowContextProvider:
    """Always returns no workflow context (M5 not yet implemented)."""

    async def active_workflow_context(
        self, *, organization_id: str, user_id: str
    ) -> tuple[str | None, str | None] | None:
        return None
