"""Hold a genuinely new image while asking "what is this photo for?" (#2 Batch Media).

Every image (not a tap answering this very picker) is held via
PendingMediaStore and the picker (channel/replies.IMAGE_PURPOSE_ROWS) is
sent instead of running understanding straight away -- a bare photo often
arrives with no caption saying what it's for, so this replaces relying on
vision analysis to guess (see docs/execution/FINANCE_MODULE_PLAN.md's note
on why that guess isn't reliable enough to be the only signal).

A burst of photos (the common case -- an engineer photographing 10 finished
bays in a row) accumulates into ONE batch: the picker is sent only for the
first photo of a fresh batch (PendingMediaStore.add_pending's
is_new_batch=True); every subsequent photo in the same burst is appended
silently (returns None here, same as any other fall-through), so the user
never sees the same picker 10 times in a row.

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
    """Returns None for anything that isn't image modality (so the caller
    falls through to the normal journey unchanged for every other modality,
    including a tap answering this exact picker, which is
    InputModality.INTERACTIVE, not IMAGE) OR for an image silently appended
    to an already-open batch."""
    if message.modality is not InputModality.IMAGE:
        return None
    result = await pending_media_store.add_pending(user_id=user_id, message=message)
    if result.capped:
        return ReplySpec(
            text=(
                f"📷 That's {result.batch_size} photos held — that's as many as I can take "
                "at once. Answer the question above for these, then send the rest."
            )
        )
    if not result.is_new_batch:
        return None
    return render_image_purpose_picker()
