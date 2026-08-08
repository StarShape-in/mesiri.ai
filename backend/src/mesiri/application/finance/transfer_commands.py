"""TransferMoney Application Command.

Local to backend (not a shared mesiri_contracts contract), mirrors
application/finance/commands.py's reasoning. Unlike ManageMoneyAccountCommand,
`from_account_id`/`to_account_id` are already real UUIDs by the time this
command exists -- the WhatsApp workflow resolves account names to ids during
slot-fill (workflows/transfer/nodes.py), before the draft is ever built, so
there is no name-based resolver step here (contrast with expense category /
account-admin's name-based resolution).

`created_by_role` travels through the draft the same way amount/from/to do
(seeded in runtime/inbound_journey.py, carried in draft.fields) so the
who-may-transfer rule can be enforced in transfer_validation.py -- a pure
Application-layer check, per architecture rule #2 ("Business rules execute
in the Domain layer, before any commit"), rather than threading actor
identity through the ExecutionDispatcher protocol for every domain.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import BaseModel


class TransferMoneyCommand(BaseModel):
    model_config = {"extra": "forbid"}

    idempotency_key: str
    organization_id: str
    created_by: str
    created_by_role: str | None = None

    from_account_id: str
    to_account_id: str
    amount: Decimal
    occurred_date: datetime.date
    description: str | None = None
    correlation_id: str | None = None
