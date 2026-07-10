"""InteractionSpec.v2 — inbound interaction intent and corrections.

Produced by the Interaction layer when classifying a user's reply to a pending
workflow confirmation. It drives the decision to resume the workflow (CONFIRM/
REJECT/CORRECTION) or route to a new journey (UNRELATED).

Ownership: SHARED ARCHITECTURE — part of the M0 contract surface. Version: v2.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

CONTRACT_VERSION = "v2"


class InteractionIntent(str, Enum):
    CONFIRM = "confirm"
    REJECT = "reject"
    CANCEL = "cancel"
    CORRECTION = "correction"
    UNRELATED = "unrelated"
    AMBIGUOUS = "ambiguous"


class FieldCorrection(BaseModel):
    """A specific field correction extracted from a user reply."""

    field_name: str
    old_value: Any | None = None
    new_value: Any | None = None


class InteractionSegment(BaseModel):
    """A distinct topical segment of the user's reply, resolved for context."""

    intent: InteractionIntent

    # The self-contained, English text representing this segment's intent.
    # The classifier must resolve any pronouns/dropped subjects from the original text.
    segment_text: str

    # Only populated if intent == CORRECTION
    corrections: list[FieldCorrection] = Field(default_factory=list)


class InteractionSpecV2(BaseModel):
    """The classified intent of a user reply to a pending workflow."""

    version: str = CONTRACT_VERSION
    correlation_id: str

    segments: list[InteractionSegment] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
