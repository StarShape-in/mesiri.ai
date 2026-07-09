"""Maps a confirmed workflow action into a typed Material Application Command (M8).

Shape-mapping only — no business validation here (that's domains/materials/
validation.py, run separately by the Handler). occurred_date is defaulted to
today because nothing upstream (CanonicalEvent/DraftAction) ever carries a
stated date; occurred_date_source records that this is an inferred value,
not a user-reported one (see migration 0220).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from mesiri_contracts.application.commands.material import (
    RecordMaterialReceiptCommand,
    RecordMaterialUsageCommand,
)
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.common.ids import new_id


def _decimal(value: object) -> Decimal:
    """Coerce a JSON-sourced numeric value (int/float/str) to Decimal safely."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return Decimal("0")


def build_command(
    confirmed: ConfirmedActionV2,
) -> RecordMaterialReceiptCommand | RecordMaterialUsageCommand:
    """Map a ConfirmedActionV2 into the typed command its action_type calls for."""
    draft = confirmed.draft_action
    fields = draft.fields
    common = {
        "command_id": new_id("cmd"),
        "idempotency_key": confirmed.workflow_instance_id,
        "correlation_id": confirmed.correlation_id,
        "organization_id": draft.organization_id,
        "project_id": draft.project_id,
        "site_id": draft.site_id,
        "material_name": str(fields.get("material_name", "")),
        "quantity": _decimal(fields.get("quantity")),
        "unit": str(fields.get("unit", "")),
        "occurred_date": date.today(),
        "occurred_date_source": "inferred_at_confirmation",
        "created_by": confirmed.confirmed_by_user_id,
    }

    if draft.action_type is DraftActionType.RECORD_MATERIAL_RECEIPT:
        return RecordMaterialReceiptCommand(
            **common,
            supplier=fields.get("supplier"),
        )
    return RecordMaterialUsageCommand(
        **common,
        work_item=fields.get("work_item"),
    )
