"""Correction deferral — documents and exports the M7 correction policy.

A *correction* is a user reply that changes a field value while a workflow
awaits confirmation — e.g. "Actually, make it 5 bags, not 4."

In M7 this is **deferred**: ``InteractionIntent.CORRECTION`` routes to
``InteractionRoute.NEW_JOURNEY`` via ``policy.decide()``, triggering a fresh
understanding journey with the corrected text. The user effectively starts a
new workflow rather than patching the pending one in-place.

When correction is fully implemented (post-M7), the logic belongs here:
    - Parse the corrected field value from the message
    - Update the pending workflow's ``collected_fields``
    - Re-run the graph to produce a new ``draft_action`` and ``pending_prompt``

Do not implement inline patching of WorkflowStateV2 until that design is
reviewed — it requires careful state versioning to avoid race conditions.
"""

from __future__ import annotations

# Sent when the user appears to be making a correction while a confirmation
# is pending. We route them to a fresh journey rather than trying to patch
# the pending workflow in M7.
CORRECTION_DEFERRED_NOTICE = (
    "It looks like you want to make a change. "
    "Please reply *YES* to confirm the current entry, *NO* to discard it, "
    "or send your corrected details as a new message after discarding."
)
