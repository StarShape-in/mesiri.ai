"""Maps a confirmed workflow action into a RecordExpenseCommand (M8-style).

Shape-mapping only — no business validation here (that's validation.py, run
separately by the Handler). occurred_date is defaulted to today because
nothing upstream (CanonicalEvent/DraftAction) ever carries a stated date,
mirroring application/materials/mapper.py.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .commands import RecordExpenseCommand


def _decimal(value: object) -> Decimal:
    """Coerce a JSON-sourced numeric value (int/float/str) to Decimal safely."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return Decimal("0")


def build_command(confirmed: ConfirmedActionV2) -> RecordExpenseCommand:
    """Map a ConfirmedActionV2 into a RecordExpenseCommand.

    `category_id` is left unset — the draft only ever carries free-text
    `category` collected in conversation, resolved server-side by
    application/expenses/resolution.py before persistence.

    `account_id`/`paid_from_own_pocket` come from the draft's collected
    fields the same way — nothing populates them yet (Finance Module Slice 1
    wires the "which account?" slot-fill that sets them), so today they are
    always absent and the command defaults to payment_status='unpaid'.
    """
    draft = confirmed.draft_action
    fields = draft.fields
    return RecordExpenseCommand(
        idempotency_key=confirmed.workflow_instance_id,
        organization_id=draft.organization_id,
        project_id=draft.project_id or "",
        site_id=draft.site_id,
        amount=_decimal(fields.get("amount")),
        category_text=str(fields.get("category", "")).strip() or None,
        vendor_text=str(fields.get("vendor", "")).strip() or None,
        account_id=fields.get("account_id"),
        paid_from_own_pocket=bool(fields.get("paid_from_own_pocket", False)),
        media_object_key=fields.get("media_object_key"),
        description=fields.get("description"),
        occurred_date=date.today(),
        source="whatsapp",
        correlation_id=confirmed.correlation_id,
        created_by=confirmed.confirmed_by_user_id,
    )
