"""Hold a genuinely new image while asking "what is this photo for?".

Every image (not a tap answering this very picker) is held via
PendingMediaStore and the picker (channel/replies.IMAGE_PURPOSE_ROWS) is
sent instead of running understanding straight away -- a bare photo often
arrives with no caption saying what it's for, so this replaces relying on
vision analysis to guess (see docs/execution/FINANCE_MODULE_PLAN.md's note
on why that guess isn't reliable enough to be the only signal).

Kept as a standalone function (not an InteractionHandler method) because it
needs PendingMediaStore, mirroring how the project/site pending-report gates
(runtime/inbound_journey.py's _run_project_gate/_run_site_gate) are plain
functions taking their store as a parameter rather than methods on
InteractionHandler -- InteractionHandler's own fast-path methods are either
I/O-free or only ever touch WorkflowRuntime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from channel.replies import ReplySpec, render_image_purpose_picker
from mesiri_contracts.assistant.enums import InputModality

if TYPE_CHECKING:
    from mesiri_contracts.assistant.normalized_message import NormalizedMessage

    from .pending_media import PendingMediaStore


async def try_hold_new_image_for_purpose_picker(
    message: NormalizedMessage, *, user_id: str, pending_media_store: PendingMediaStore
) -> ReplySpec | None:
    """Returns None for anything that isn't image modality, so the caller
    falls through to the normal journey unchanged for every other
    modality (including a tap answering this exact picker, which is
    InputModality.INTERACTIVE, not IMAGE)."""
    if message.modality is not InputModality.IMAGE:
        return None
    await pending_media_store.set_pending(user_id=user_id, message=message)
    return render_image_purpose_picker()
