"""RecordExpense Application Command.

Local to backend (not a shared mesiri_contracts contract) — since backend is
imported in-process by apps/whatsapp-assistant (see how Materials' dispatcher
is wired in runtime/dependencies.py), this command doesn't need to live in
shared/contracts for the WhatsApp path to reach it.

`category_id` is set directly by the REST path (the client already knows the
id — see domains/expenses/router.py). The WhatsApp path only has free-text
category input at draft time, so it sends `category_text` instead and leaves
`category_id` unset; application/expenses/resolution.py resolves it before
persistence, mirroring how Materials resolves material_name/unit into
material_id/unit_id (see application/materials/resolution.py).

`account_id`/`paid_from_own_pocket` are the paid-from choice (Finance Module
Slice 0): naming an account records a payment against it; `paid_from_own_pocket`
means the payer covered it personally (payment_status='reimbursable', no
ledger entry yet — see infrastructure/postgres/repositories/expense_execution.py);
leaving both unset means payment_status stays 'unpaid'. Mutually exclusive —
enforced in validation.py.

`media_object_key` is the receipt/bill photo's object-storage key, when the
expense was reported from a WhatsApp image tapped as "Expense" in the
image-purpose picker (see canonicalization/builder.py's generic
`media_object_key` field carry-through and interactions/image_purpose.py).
Optional — most expenses are still typed/spoken with no image at all.

`vendor_id`/`vendor_text` follow the same split as category_id/category_text
above -- the WhatsApp path only has free-text vendor input ("paid ABC
Hardware ₹500"), resolved into vendor_id by
application/vendors/resolution.py before persistence. Unlike category, an
absent vendor_text is left unresolved (vendor_id stays None) rather than
falling back to a default -- see that module's docstring.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import BaseModel


class RecordExpenseCommand(BaseModel):
    model_config = {"extra": "forbid"}

    idempotency_key: str
    organization_id: str
    project_id: str
    amount: Decimal
    created_by: str

    category_id: str | None = None
    category_text: str | None = None
    vendor_id: str | None = None
    vendor_text: str | None = None
    account_id: str | None = None
    paid_from_own_pocket: bool = False
    media_object_key: str | None = None
    site_id: str | None = None
    currency: str = "INR"
    description: str | None = None
    occurred_date: datetime.date
    occurred_time: datetime.time | None = None
    source: str = "web"
    source_message_id: str | None = None
    correlation_id: str | None = None
