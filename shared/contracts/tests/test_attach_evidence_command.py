"""AttachEvidenceCommand contract (#2 Batch Media) -- the shape a batch of
Site Update photos is attached from.

Pure Pydantic construction -- the SQL side (PostgresProgressExecutionRepository
.persist_attach_evidence) needs a live database and is not covered here, same
scoping decision as this codebase's other Postgres-only repository methods.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mesiri_contracts.application.commands.progress import AttachEvidenceCommand

ORG = "11111111-1111-4111-8111-111111111111"
ACTIVITY = "33333333-3333-4333-8333-333333333333"
USER = "22222222-2222-4222-8222-222222222222"


def _cmd(**overrides) -> AttachEvidenceCommand:
    fields = {
        "command_id": "cmd_1",
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "activity_id": ACTIVITY,
        "media_object_keys": ["media/wamid.1/a", "media/wamid.2/b"],
        "uploaded_by": USER,
    }
    fields.update(overrides)
    return AttachEvidenceCommand(**fields)


def test_constructs_with_a_batch_of_keys():
    cmd = _cmd()
    assert cmd.media_object_keys == ["media/wamid.1/a", "media/wamid.2/b"]
    assert cmd.caption is None
    assert cmd.mime_type is None


def test_constructs_with_a_single_key():
    cmd = _cmd(media_object_keys=["media/wamid.1/a"])
    assert cmd.media_object_keys == ["media/wamid.1/a"]


def test_carries_no_idempotency_key_field_at_all():
    """Deliberate -- unlike CreateActivityCommand/AddProgressUpdateCommand,
    evidence attach never goes through the confirm/execute idempotency-key
    path (see the command's own docstring). extra='forbid' means passing
    one would raise, not silently be ignored."""
    with pytest.raises(ValidationError):
        AttachEvidenceCommand(
            command_id="cmd_1",
            idempotency_key="should_not_exist",
            correlation_id="cor_1",
            organization_id=ORG,
            activity_id=ACTIVITY,
            media_object_keys=["media/a"],
            uploaded_by=USER,
        )


def test_caption_and_mime_type_are_optional_but_settable():
    cmd = _cmd(caption="Poured slab, north corner", mime_type="image/jpeg")
    assert cmd.caption == "Poured slab, north corner"
    assert cmd.mime_type == "image/jpeg"
