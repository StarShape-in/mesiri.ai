from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel


class MaterialReceiptResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    site_id: uuid.UUID | None
    material_name: str
    quantity: Decimal
    unit: str
    unit_cost: Decimal | None
    total_cost: Decimal | None
    supplier: str | None
    occurred_date: datetime.date
    occurred_time: datetime.time | None
    correlation_id: str | None
    source: str
    occurred_date_source: str
    material_id: uuid.UUID | None
    created_at: datetime.datetime
    created_by: uuid.UUID
    updated_at: datetime.datetime
    updated_by: uuid.UUID | None


class MaterialReceiptsListResponse(BaseModel):
    items: list[MaterialReceiptResponse]
    total: int


class MaterialUsageResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    site_id: uuid.UUID | None
    material_name: str
    quantity: Decimal
    unit: str
    work_item: str | None
    occurred_date: datetime.date
    occurred_time: datetime.time | None
    correlation_id: str | None
    source: str
    occurred_date_source: str
    material_id: uuid.UUID | None
    created_at: datetime.datetime
    created_by: uuid.UUID
    updated_at: datetime.datetime
    updated_by: uuid.UUID | None


class MaterialUsageListResponse(BaseModel):
    items: list[MaterialUsageResponse]
    total: int


class MaterialStockResponse(BaseModel):
    organization_id: uuid.UUID
    project_id: uuid.UUID
    site_id: uuid.UUID | None
    material_name: str
    unit: str
    total_received: Decimal
    total_used: Decimal
    current_stock: Decimal
