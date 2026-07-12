"""Maps a confirmed record into the shared receipt-card data shape.

Pure, no I/O -- one function per DraftActionType, all producing the same
generic shape (brand/category/value/subtitle/location/dateTime/sections/
footer) so template.py renders every record type through one layout, never
a different image per kind (the whole point of this feature -- see the
Module Placement Log entry in AGENTS.md).

Field labels/icons here are display concerns, not business logic -- adding a
new DraftActionType means adding a case here, never touching the domain
layer or the template.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2


@dataclass(frozen=True, slots=True)
class ReceiptField:
    icon: str  # key into template.py's _ICONS
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class ReceiptLocationRow:
    icon: str
    text: str


@dataclass(frozen=True, slots=True)
class ReceiptData:
    brand: str
    category: str
    value: str
    subtitle: str
    location: list[ReceiptLocationRow]
    date: str
    time: str
    sections: list[list[ReceiptField]]
    id_label: str
    record_id: str
    saved_at: str
    logo_text: str


def _project_name(project_id: str | None, projects: list[Any]) -> str | None:
    if not project_id:
        return None
    return next((p.name for p in projects if p.id == project_id), None)


def _site_name(site_id: str | None, sites: list[Any]) -> str | None:
    if not site_id:
        return None
    return next((s.name for s in sites if s.id == site_id), None)


def _fmt_quantity(fields: dict) -> str:
    quantity = fields.get("quantity", "")
    unit = fields.get("unit", "")
    return f"{quantity} {unit}".strip()


def build_receipt_data(
    draft: DraftActionV2,
    *,
    material_row_id: str,
    reporter_name: str | None,
    projects: list[Any],
    sites: list[Any],
    confirmed_at: datetime,
) -> ReceiptData:
    """Build the generic receipt shape for a confirmed DraftAction.

    ``material_row_id`` comes from ExecutionResult, not the draft -- it's the
    real persisted row id, so the receipt's "Record id" points at something
    that actually exists in material_receipts/material_usage.
    """
    fields = draft.fields
    material_name = str(fields.get("material_name", "")).strip() or "Material"
    project_name = _project_name(draft.project_id, projects) or "—"
    site_name = _site_name(draft.site_id, sites) or "—"
    reporter = reporter_name or "—"

    location = [
        ReceiptLocationRow("building", project_name),
        ReceiptLocationRow("pin", site_name),
    ]

    if draft.action_type is DraftActionType.RECORD_MATERIAL_RECEIPT:
        category = "Material receipt"
        subtitle = f"{material_name.title()} received"
        sections = [
            [
                ReceiptField("layers", "Material", material_name.title()),
                ReceiptField("store", "Supplier", str(fields.get("supplier") or "—")),
            ],
            [
                ReceiptField("user", "Reported by", reporter),
                ReceiptField("whatsapp", "Source", "WhatsApp"),
            ],
        ]
        id_prefix = "MR"
    else:
        category = "Material usage"
        subtitle = f"{material_name.title()} used"
        sections = [
            [
                ReceiptField("layers", "Material", material_name.title()),
                ReceiptField("hammer", "Used for", str(fields.get("work_item") or "—")),
            ],
            [
                ReceiptField("user", "Reported by", reporter),
                ReceiptField("whatsapp", "Source", "WhatsApp"),
            ],
        ]
        id_prefix = "MU"

    record_id = f"{id_prefix}-{confirmed_at:%d%m%y}-{material_row_id.replace('-', '')[:4].upper()}"

    return ReceiptData(
        brand="MESIRI",
        category=category,
        value=_fmt_quantity(fields),
        subtitle=subtitle,
        location=location,
        date=f"{confirmed_at:%d %b %Y}",
        time=f"{confirmed_at:%I:%M %p}",
        sections=sections,
        id_label="Record id",
        record_id=record_id,
        saved_at=f"{confirmed_at:%d %b %Y · %I:%M %p}",
        logo_text="MESIRI AI",
    )
