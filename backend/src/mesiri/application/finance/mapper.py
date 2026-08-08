"""Maps a confirmed workflow action into a ManageMoneyAccountCommand.

Shape-mapping only — no business validation here (that's validation.py, run
separately by the Handler). Mirrors application/expenses/mapper.py.
"""

from __future__ import annotations

from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2

from .commands import ManageMoneyAccountCommand


def build_command(confirmed: ConfirmedActionV2) -> ManageMoneyAccountCommand:
    draft = confirmed.draft_action
    fields = draft.fields
    return ManageMoneyAccountCommand(
        idempotency_key=confirmed.workflow_instance_id,
        organization_id=draft.organization_id,
        created_by=confirmed.confirmed_by_user_id,
        created_by_role=fields.get("created_by_role"),
        action=str(fields.get("action", "")),
        name=fields.get("name"),
        account_type=str(fields.get("account_type") or "cash"),
        target_name=fields.get("target_name"),
        new_name=fields.get("new_name"),
        correlation_id=confirmed.correlation_id,
    )
