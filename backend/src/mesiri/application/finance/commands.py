"""ManageMoneyAccount Application Command — create / rename / deactivate.

Local to backend (not a shared mesiri_contracts contract), mirrors
application/expenses/commands.py's reasoning: backend is imported in-process
by apps/whatsapp-assistant, so this command doesn't need to live in
shared/contracts for the WhatsApp path to reach it. There is no REST entry
point for this command in this phase (see docs/execution/FINANCE_MODULE_PLAN.md) --
WhatsApp/CQRS is the only caller.

`target_account_id` is populated by resolution.py's PostgresAccountLookupResolver
(rename/deactivate resolve the target account by name before persistence);
`create` never sets it since it always makes a fresh account.
"""

from __future__ import annotations

from pydantic import BaseModel


class ManageMoneyAccountCommand(BaseModel):
    model_config = {"extra": "forbid"}

    idempotency_key: str
    organization_id: str
    created_by: str
    created_by_role: str | None = None
    action: str  # "create" | "rename" | "deactivate"

    # create
    name: str | None = None
    account_type: str = "cash"

    # rename / deactivate — identify the existing account by name; resolved
    # to target_account_id before persist_success ever runs.
    target_name: str | None = None
    new_name: str | None = None  # rename only
    target_account_id: str | None = None

    correlation_id: str | None = None
