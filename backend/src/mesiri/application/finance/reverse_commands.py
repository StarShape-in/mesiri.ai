"""ReverseTransaction Application Command.

Local to backend (not a shared mesiri_contracts contract), mirrors
application/finance/transfer_commands.py's reasoning. `expense_id`/
`money_transaction_id` are already real UUIDs by the time this command
exists -- runtime/inbound_journey.py's seeding step resolves "the most
recent expense/transfer" into a concrete id before the draft is ever built
(see workflows/reverse/nodes.py), mirroring how transfer's account ids are
resolved before its draft.

`created_by_role` travels through the draft the same way transfer's does
(seeded in runtime/inbound_journey.py, carried in draft.fields) so the
who-may-reverse rule can be enforced in reverse_validation.py.
"""

from __future__ import annotations

from pydantic import BaseModel


class ReverseTransactionCommand(BaseModel):
    model_config = {"extra": "forbid"}

    idempotency_key: str
    organization_id: str
    created_by: str
    created_by_role: str | None = None

    target_kind: str  # "expense" | "transfer"
    expense_id: str | None = None
    money_transaction_id: str | None = None

    correlation_id: str | None = None
