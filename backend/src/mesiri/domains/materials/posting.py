"""Canonical material-movement posting (Materials V2 ledger).

The one function every write path calls to post a RECEIPT/ISSUE movement,
so material_receipts/material_usage inserts and their corresponding
material_movements insert happen on the same connection/transaction and are
therefore atomic by construction — no new transaction abstraction needed,
just reuse whichever atomicity mechanism the caller already has (the REST
router's ambient per-request connection, or the CQRS handler's explicit
`db.transaction()` block).

Movements are immutable: this module only ever INSERTs. Corrections call
this same function with the OPPOSITE movement_type of what they reverse and
`reversal_of_movement_id` set, matching the opposite-direction-row
convention migration 0270 already established for material_receipts/
material_usage reversals.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncConnection

from mesiri.infrastructure.postgres.repositories.materials import MaterialMovementsRepository

MOVEMENT_TYPES = ("RECEIPT", "ISSUE")


async def post_material_movement(
    conn: AsyncConnection,
    *,
    movement_type: str,
    material_id: uuid.UUID,
    unit_id: uuid.UUID,
    quantity: Decimal,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    site_id: uuid.UUID | None,
    occurred_at: datetime.datetime,
    source_type: str,
    source_id: uuid.UUID,
    recorded_by_user_id: uuid.UUID,
    reversal_of_movement_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
) -> dict:
    if movement_type not in MOVEMENT_TYPES:
        raise ValueError(f"Invalid movement_type: {movement_type!r}")
    if quantity <= 0:
        raise ValueError("quantity must be positive; direction is carried by movement_type")

    repo = MaterialMovementsRepository(conn)
    return await repo.insert(
        movement_id=uuid.uuid4(),
        organization_id=organization_id,
        project_id=project_id,
        site_id=site_id,
        material_id=material_id,
        unit_id=unit_id,
        movement_type=movement_type,
        quantity=quantity,
        occurred_at=occurred_at,
        source_type=source_type,
        source_id=source_id,
        recorded_by_user_id=recorded_by_user_id,
        reversal_of_movement_id=reversal_of_movement_id,
        idempotency_key=idempotency_key,
    )


def opposite_movement_type(movement_type: str) -> str:
    """The movement_type a reversal of `movement_type` must carry."""
    return "ISSUE" if movement_type == "RECEIPT" else "RECEIPT"
