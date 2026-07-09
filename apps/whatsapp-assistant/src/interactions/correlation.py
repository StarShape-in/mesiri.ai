"""Correlation — matches an incoming reply to a pending workflow instance.

In M7, the single-active-confirmation invariant guarantees that a user has
at most one AWAITING_CONFIRMATION workflow at any time. Correlation is
therefore trivial: if the user has a pending workflow, any classified reply
is correlated to it — no explicit message-ID tracking is needed.

Future extension: if the single-active invariant is ever relaxed (multiple
concurrent pending workflows per user), add a ``pending_message_id`` field
to WorkflowStateV2, record the WhatsApp message ID of the outbound
confirmation, and implement ID-based matching here. The interface is stable
for that extension — callers use ``is_correlated()`` and never inline the
matching logic.
"""

from __future__ import annotations

from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from workflows.ports import LoadedWorkflowInstance


def is_correlated(message: NormalizedMessage, loaded: LoadedWorkflowInstance) -> bool:  # noqa: ARG001
    """Return True if ``message`` is correlated to ``loaded``.

    M7 implementation: always True when a pending instance is present.
    The single-active invariant makes explicit ID matching unnecessary.
    """
    return True
