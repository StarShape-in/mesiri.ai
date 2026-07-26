from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    site_id: uuid.UUID | None
    category_id: uuid.UUID
    category_name: str | None = None
    amount: Decimal
    currency: str
    description: str | None
    occurred_date: datetime.date
    occurred_time: datetime.time | None
    workflow_status: str
    payment_status: str
    source: str
    source_message_id: str | None
    correlation_id: str | None
    created_by: uuid.UUID


class RecordExpenseResponse(BaseModel):
    id: uuid.UUID
    status: str
