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
    site_id: str | None = None
    currency: str = "INR"
    description: str | None = None
    occurred_date: datetime.date
    occurred_time: datetime.time | None = None
    source: str = "web"
    source_message_id: str | None = None
    correlation_id: str | None = None
