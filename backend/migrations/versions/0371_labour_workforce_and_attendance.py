"""Add the real Labour schema: workforce register + attendance reports/lines/attachments.

Supersedes 0120's `labour_attendance`/`labour_attendance_entries` rather than
extending them (ADR-L1, docs/plans/labour-module-implementation-plan.md §2.2 /
§5) — those tables enforce one row per site per day, which cannot express
append-only attendance history, and store worker names as free text with no
register link. They are unused by any code and are left in place untouched;
no destructive drop, no data migration. Because the old names are still live,
the new tables use different names (``labour_attendance_reports``, not
``labour_attendance``) so the two schemas can never collide or be confused.

Four tables, mirroring two established patterns exactly rather than
inventing new ones:

**workforce_workers** — the mutable register (Material's thin-domain style:
plain columns, no JSONB). Deliberately minimal: name, trade, worker_type,
default_daily_wage, contractor (free text — Q2, resolved 2026-07-25),
status. No address, ID documents, bank details or next of kin — this is
operational reference data, not an HR record (see domains/workforce/workers.py).

**labour_attendance_reports** — one row per WhatsApp report, append-only.
A second report for the same site and day is a second row, never an update
to the first (principle P5) — this is the entire reason 0120 had to be
superseded rather than reused. Each report carries its own id (the
"Attendance ID"), which is also what a future correction workflow references
via `corrects_report_id` — a nullable self-reference so a correction can point
back at what it corrects without either row ever being mutated. Not built
yet, but the column is here now because provenance cannot be added
retroactively (principle P8) and this is the cheapest moment to reserve it.

`recorded_via` distinguishes how the report arrived (whatsapp_text /
whatsapp_voice / whatsapp_image / dashboard) — simple metadata with no
bearing on the schema shape, but valuable later for debugging AI accuracy per
input path and for the dashboard's own future write path (labour-dashboard-plan.md
§1: dashboard entry, if ever built, goes through the same tables).

**labour_attendance_lines** — one row per line of a report: either a named
worker (worker_name set) or a headcount group (worker_name null, headcount
> 1). `worker_id` links to the register when matched, and is nullable for a
temporary worker or a group — attendance never writes the register, so this
FK is the only relationship between the two tables in either direction
(principle P1). `trade` and `daily_wage` are copied onto the line rather than
read from the register at query time (principle P5's corollary): editing a
worker's wage next month must never rewrite what last month's attendance
appears to have cost.

**labour_attendance_attachments** — identical shape to expense_attachments
(ADR-L3), so Timeline and Image Gallery integration come for free later by
consuming the same attachment pattern they already consume for receipts.

All four tables get `ON DELETE CASCADE` from their reachable path down to
`organizations.id` directly in this migration (workforce_workers and
labour_attendance_reports from organization_id; the two child tables from
their parent), so 0361's cascade-delete guarantee holds for Labour without
a follow-up migration.

Revision ID: 0371
Revises: 0370
Create Date: 2026-07-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0371"
down_revision = "0370"
branch_labels = None
depends_on = None


def _audit_columns(*, mutable: bool) -> list[sa.Column]:
    """created_at/created_by always; updated_at/updated_by only for rows that
    are actually ever updated. Attendance reports and lines are immutable
    (principle P5) and never gain an updated_by, so no column exists to
    misuse for a "correction" that should instead be a new report."""
    columns = [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    ]
    if mutable:
        columns.append(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            )
        )
        columns.append(
            sa.Column("updated_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True)
        )
    return columns


def upgrade() -> None:
    # --- workforce_workers: the editable register --------------------------
    op.create_table(
        "workforce_workers",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("trade", sa.String(), nullable=True),
        sa.Column("worker_type", sa.String(), nullable=False, server_default="permanent"),
        sa.Column("default_daily_wage", sa.Numeric(14, 2), nullable=True),
        sa.Column("contractor", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        *_audit_columns(mutable=True),
    )
    op.create_index("ix_workforce_workers_organization_id", "workforce_workers", ["organization_id"])
    op.create_index(
        "ix_workforce_workers_org_status", "workforce_workers", ["organization_id", "status"]
    )
    op.create_check_constraint(
        "ck_workforce_workers_worker_type",
        "workforce_workers",
        "worker_type IN ('permanent', 'temporary', 'contractor')",
    )
    op.create_check_constraint(
        "ck_workforce_workers_status",
        "workforce_workers",
        "status IN ('active', 'inactive')",
    )

    # --- labour_attendance_reports: one immutable row per report -----------
    op.create_table(
        "labour_attendance_reports",
        # The Attendance ID -- the durable reference for this report, and
        # what a future correction (a new report) points back at via
        # corrects_report_id below.
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
        sa.Column("occurred_date", sa.Date(), nullable=False),
        # How the report arrived. Not a foreign key to InputModality (the
        # assistant-side enum) -- dashboard entry has no modality, and this
        # column must not need a migration every time a new capture path is
        # added on the application side.
        sa.Column("recorded_via", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        # Optional, self-referencing: set when this report is an explicit
        # correction of an earlier one. Both rows stand -- this is a pointer,
        # never a rewrite (principle P5). No correction workflow exists yet;
        # the column is reserved so building one later needs no schema change.
        sa.Column(
            "corrects_report_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("labour_attendance_reports.id"),
            nullable=True,
        ),
        sa.Column("correlation_id", sa.String(), nullable=True),
        *_audit_columns(mutable=False),
    )
    op.create_index(
        "ix_labour_attendance_reports_org_project",
        "labour_attendance_reports",
        ["organization_id", "project_id"],
    )
    op.create_index(
        "ix_labour_attendance_reports_site_id", "labour_attendance_reports", ["site_id"]
    )
    op.create_index(
        "ix_labour_attendance_reports_occurred_date",
        "labour_attendance_reports",
        ["occurred_date"],
    )
    op.create_index(
        "ix_labour_attendance_reports_correlation_id",
        "labour_attendance_reports",
        ["correlation_id"],
    )
    # Deliberately NOT unique on (site_id, occurred_date) -- that constraint
    # is exactly what made 0120 unusable (§2.2). Two reports for the same
    # site and day are both kept.
    op.create_check_constraint(
        "ck_labour_attendance_reports_recorded_via",
        "labour_attendance_reports",
        "recorded_via IN ('whatsapp_text', 'whatsapp_voice', 'whatsapp_image', 'dashboard')",
    )

    # --- labour_attendance_lines: named person OR headcount group ----------
    op.create_table(
        "labour_attendance_lines",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "report_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("labour_attendance_reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Set only when matching resolved this line to a register entry.
        # NULL means "not in the register" -- a genuinely new person or a
        # headcount group -- and is never written to as a side effect of
        # saving attendance (principle P1: promotion is a separate act).
        sa.Column(
            "worker_id", sa.UUID(as_uuid=True), sa.ForeignKey("workforce_workers.id"), nullable=True
        ),
        sa.Column("worker_name", sa.String(), nullable=True),
        # The name exactly as written, when the source wasn't Latin script.
        # Kept because transliteration has no single right answer and the
        # supervisor who can read both is the one person able to verify it.
        sa.Column("worker_name_original", sa.String(), nullable=True),
        # Copied at the moment of recording, not read from workforce_workers
        # at query time -- editing a worker's trade or wage next month must
        # never change what last month's attendance appears to have been.
        sa.Column("trade", sa.String(), nullable=True),
        sa.Column("headcount", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("daily_wage", sa.Numeric(14, 2), nullable=True),
        sa.Column("contractor", sa.String(), nullable=True),
        # Optional link to the activity/work item this line worked on
        # (principle P7). Free text -- no activities table exists yet, and
        # this is not the migration that builds one; the value is carried
        # now because it cannot be reconstructed after the fact.
        sa.Column("activity", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_labour_attendance_lines_report_id", "labour_attendance_lines", ["report_id"])
    op.create_index("ix_labour_attendance_lines_worker_id", "labour_attendance_lines", ["worker_id"])
    op.create_check_constraint(
        "ck_labour_attendance_lines_headcount_positive",
        "labour_attendance_lines",
        "headcount > 0",
    )
    op.create_check_constraint(
        "ck_labour_attendance_lines_daily_wage_non_negative",
        "labour_attendance_lines",
        "daily_wage IS NULL OR daily_wage >= 0",
    )

    # --- labour_attendance_attachments: identical shape to expense_attachments
    op.create_table(
        "labour_attendance_attachments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "report_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("labour_attendance_reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("media_object_key", sa.String(), nullable=False),
        sa.Column("attachment_type", sa.String(), nullable=False, server_default="attendance_sheet"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index(
        "ix_labour_attendance_attachments_report_id",
        "labour_attendance_attachments",
        ["report_id"],
    )
    op.create_check_constraint(
        "ck_labour_attendance_attachments_type",
        "labour_attendance_attachments",
        "attachment_type IN ('attendance_sheet', 'other')",
    )


def downgrade() -> None:
    op.drop_table("labour_attendance_attachments")
    op.drop_table("labour_attendance_lines")
    op.drop_table("labour_attendance_reports")
    op.drop_table("workforce_workers")
