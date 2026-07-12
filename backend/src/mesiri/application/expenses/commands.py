"""RecordExpense Application Command.

Local to backend (not a shared mesiri_contracts contract) — unlike Materials,
expenses has no WhatsApp/Planner producer yet, so there is no cross-package
consumer that needs this shape. If/when a WhatsApp or Planner integration is
added, promote this into shared/contracts following the Materials precedent.
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
    category_id: str
    amount: Decimal
    created_by: str

    site_id: str | None = None
    currency: str = "INR"
    description: str | None = None
    occurred_date: datetime.date
    occurred_time: datetime.time | None = None
    source: str = "web"
    source_message_id: str | None = None
    correlation_id: str | None = None
