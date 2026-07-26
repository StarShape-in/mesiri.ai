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
    # Petty cash issued to or returned by a person (e.g. "give ₹20,000
    # petty cash to Alan", "Alan returns ₹3,000") -- built as a convenience
    # shape over TRANSFER (Finance Module Slice 5, see
    # workflows/petty_cash/nodes.py): the recipient's employee-advance
    # account is one leg of the transfer, auto-created on first issuance.
    # Splits into two CanonicalEventTypes by the extracted `direction` field
    # ("issue" or "return"), the same way MATERIAL_UPDATE splits by
    # `direction` (see canonicalization/mapping.py).
    PETTY_CASH = "petty_cash"
    # Undo the user's most recently recorded expense or transfer (e.g.
    # "reverse my last expense", "cancel that transfer") -- Finance Module
    # Slice 7. Splits into two CanonicalEventTypes by the extracted
    # `target_kind` field ("expense" or "transfer"), the same way
    # MATERIAL_UPDATE/PETTY_CASH split by their own field (see
    # canonicalization/mapping.py). Deliberately targets only the *most
    # recent* record of that kind -- no slot-fill/disambiguation UI for
    # picking among several, per the V1 scope in
    # docs/execution/FINANCE_MODULE_PLAN.md.
    REVERSAL = "reversal"
    # Managing the org's own money accounts themselves -- create/rename/
    # deactivate (e.g. "rename Main HDFC Bank Account to Office Cash") --
    # never a transaction against one. Until 2026-07-26 this bypassed
    # Understanding entirely (a hand-written English-only regex parser,
    # runtime/account_admin_parser.py, still runs first as a zero-token fast
    # path for the exact phrasing it recognizes); this semantic type is the
    # AI-understood fallback for everything else -- other phrasing, voice,
    # non-English -- the same as every other finance workflow. ADMIN/FINANCE
    # only, enforced independently of Understanding (see
    # runtime/inbound_journey.py and application/finance/validation.py) --
    # this type alone existing here does not grant a lower-privileged role
    # the ability to act on it.
    ACCOUNT_ADMIN = "account_admin"
    UNKNOWN = "unknown"
