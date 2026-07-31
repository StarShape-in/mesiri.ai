"""Supplier invoices for materials: one document, many purchases, one expense.

A supplier invoice is one piece of paper listing several materials. Recording
it as a single blob would make inventory and material history unusable, so this
follows the shape `labour_attendance_reports` -> `labour_attendance_lines`
already proved (migration `0371`): a parent document row, one child row per
line, and attachments hanging off the parent.

    material_invoices                  (the document: supplier, date, total)
      -> material_receipts.invoice_id  (one purchase per material, as before)
      -> material_invoice_attachments  (the original image/PDF as evidence)
      -> expenses.id via expense_id    (the money owed, created by Finance)

Three deliberate choices:

**`material_receipts` gains only a nullable `invoice_id`.** Every existing write
path -- the dashboard's single-material form, the WhatsApp assistant, historic
rows -- keeps working untouched, and no backfill invents documents that were
never photographed. A purchase without an invoice is a normal, permanent state,
not a gap to be filled later.

**`material_invoice_attachments` mirrors `expense_attachments` exactly**, which
is the convention `progress_attachments` already established ("evidence pattern
reuse", migration `0430`). It stores a `media_object_key`, never bytes: the file
already lives in object storage, uploaded once at WhatsApp ingress, and both
Materials and Finance reference that same key. One file, several referrers.

**`expense_id` links to Finance rather than duplicating it.** Materials never
writes into the expenses table -- it calls Finance's own handler and stores the
id it gets back, so there is exactly one source of truth for what is owed and no
second confirmation for the user. `material_invoices.invoice_total` is stored as
printed on the document and is deliberately NOT reconciled against the sum of
its lines: tax and freight are not extracted (V1 scope), so those two figures
legitimately differ and treating the gap as an error would flag nearly every
real invoice.

Revision ID: 0461
Revises: 0460
Create Date: 2026-07-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0461"
down_revision = "0460"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "material_invoices",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id", sa.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False
        ),
        sa.Column("site_id", sa.UUID(as_uuid=True), sa.ForeignKey("sites.id"), nullable=True),
        # Nullable: the supplier may not match a vendor record, and blocking the
        # purchase on tidying the vendor list would push people back to paper.
        sa.Column("vendor_id", sa.UUID(as_uuid=True), sa.ForeignKey("vendors.id"), nullable=True),
        # Always kept, even when vendor_id resolves -- the document's own words
        # are evidence and must survive a later vendor rename or merge.
        sa.Column("supplier_name", sa.String(), nullable=True),
        sa.Column("invoice_number", sa.String(), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        # As printed. Never derived from the lines -- see the module docstring.
        sa.Column("invoice_total", sa.Numeric(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        # The Finance expense this invoice created. Nullable because an invoice
        # recorded before Finance is reachable is still a valid purchase record.
        sa.Column("expense_id", sa.UUID(as_uuid=True), sa.ForeignKey("expenses.id"), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="web"),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("created_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index(
        "ix_material_invoices_org_project", "material_invoices", ["organization_id", "project_id"]
    )
    op.create_index(
        "ix_material_invoices_org_date", "material_invoices", ["organization_id", "invoice_date"]
    )
    op.create_index("ix_material_invoices_vendor_id", "material_invoices", ["vendor_id"])

    # Mirrors expense_attachments' shape exactly (evidence pattern reuse).
    op.create_table(
        "material_invoice_attachments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "invoice_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("material_invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("media_object_key", sa.String(), nullable=False),
        sa.Column("attachment_type", sa.String(), nullable=False, server_default="bill"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("created_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index(
        "ix_material_invoice_attachments_invoice_id",
        "material_invoice_attachments",
        ["invoice_id"],
    )

    op.add_column(
        "material_receipts",
        sa.Column(
            "invoice_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("material_invoices.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_material_receipts_invoice_id", "material_receipts", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_material_receipts_invoice_id", table_name="material_receipts")
    op.drop_column("material_receipts", "invoice_id")
    op.drop_index(
        "ix_material_invoice_attachments_invoice_id", table_name="material_invoice_attachments"
    )
    op.drop_table("material_invoice_attachments")
    op.drop_index("ix_material_invoices_vendor_id", table_name="material_invoices")
    op.drop_index("ix_material_invoices_org_date", table_name="material_invoices")
    op.drop_index("ix_material_invoices_org_project", table_name="material_invoices")
    op.drop_table("material_invoices")
