"""Material domain validation (M8) — pure functions, no I/O, no SQL.

Uses only fields the schema actually has. No unit-of-measure conversion, no
stock/balance check (materials_catalog intentionally has no balance table
yet — see migration 0180's docstring). Runs in the Application Handler
*before* any transaction opens (validation needs no connection at all).
"""

from __future__ import annotations

from mesiri_contracts.application.commands.material import (
    RecordMaterialReceiptCommand,
    RecordMaterialUsageCommand,
)


def validate_receipt(cmd: RecordMaterialReceiptCommand) -> list[str]:
    """Return violation reasons; empty list means valid."""
    reasons: list[str] = []
    if cmd.project_id is None:
        reasons.append("project is not resolved")
    if cmd.quantity <= 0:
        reasons.append("quantity must be positive")
    if not cmd.material_name.strip():
        reasons.append("material_name is required")
    if not cmd.unit.strip():
        reasons.append("unit is required")
    return reasons


def validate_usage(cmd: RecordMaterialUsageCommand) -> list[str]:
    """Return violation reasons; empty list means valid."""
    reasons: list[str] = []
    if cmd.project_id is None:
        reasons.append("project is not resolved")
    if cmd.quantity <= 0:
        reasons.append("quantity must be positive")
    if not cmd.material_name.strip():
        reasons.append("material_name is required")
    if not cmd.unit.strip():
        reasons.append("unit is required")
    return reasons


def validate(cmd: RecordMaterialReceiptCommand | RecordMaterialUsageCommand) -> list[str]:
    """Single dispatch entry point the Handler calls — before any transaction opens."""
    if isinstance(cmd, RecordMaterialReceiptCommand):
        return validate_receipt(cmd)
    return validate_usage(cmd)
