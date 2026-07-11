"""Shared assistant enumerations (input modality, semantic type).

``InputModality`` is used by both ``NormalizedMessage`` (M2, produced) and
``UnderstandingResult`` (M3, consumed) so it lives here to avoid divergence.

Ownership: CROSS-REVIEW (shared between M2 producer and M3 consumer).
"""

from __future__ import annotations

from enum import Enum


class InputModality(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    DOCUMENT = "document"
    INTERACTIVE = "interactive"  # button / list reply
    UNKNOWN = "unknown"


class SemanticType(str, Enum):
    """What the understanding pipeline believes the message is *about*.

    These are understanding hypotheses, not workflow selections — the planner
    (M6) owns final workflow choice.
    """

    EXPENSE = "expense"
    EQUIPMENT_USAGE = "equipment_usage"
    MATERIAL_UPDATE = "material_update"
    LABOUR_UPDATE = "labour_update"
    GENERAL_SITE_UPDATE = "general_site_update"
    GENERAL_QUESTION = "general_question"
    # A deterministically recognized "who am i"/"my profile"/etc (see
    # mesiri_ai.whoami_classifier) -- distinct from GENERAL_QUESTION/UNKNOWN
    # so the answer is the caller's own identity summary, not the generic
    # capability reply or an undifferentiated "didn't understand". Set
    # without an AI call; the reply itself is still built downstream
    # (runtime/inbound_journey.py), since it needs the resolved
    # ActorIdentity, which Understanding must not know about.
    WHOAMI_QUESTION = "whoami_question"
    UNKNOWN = "unknown"
