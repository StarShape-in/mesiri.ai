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
    # A question about current stock or movement history for a material (e.g.
    # "how much cement is left?") -- read-only, never an update. Distinct from
    # MATERIAL_UPDATE the same way WHOAMI_QUESTION is distinct from a report:
    # it carries no business record to save, only a query to answer.
    INVENTORY_QUERY = "inventory_query"
    # A question about cash/account balances or past expenses (e.g. "how much
    # cash do I have?", "balance of Site Cash", "how much did we spend on
    # diesel?") -- read-only, never an update. Splits into two
    # CanonicalEventTypes by the extracted `query_kind` field ("balance" or
    # "expenses"), the same way MATERIAL_UPDATE splits by `direction` (see
    # canonicalization/mapping.py).
    FINANCE_QUERY = "finance_query"
    # Moving money between two of the org's own accounts (e.g. "transfer
    # ₹50,000 from Company Account to Site Cash") -- a business-affecting
    # write, unlike FINANCE_QUERY, so it still goes through draft/confirm.
    TRANSFER = "transfer"
    UNKNOWN = "unknown"
