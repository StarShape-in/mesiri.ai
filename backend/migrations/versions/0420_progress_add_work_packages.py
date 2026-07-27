"""Add work_packages + work_package_planned_items — the planning layer.

Part of the Daily Reporting module (docs/execution/DAILY_REPORTING_PLAN.md).
Created now, ahead of the Phase 9 feature that populates it, purely so
`activities.work_package_id` (0430) has a real FK target from day one rather
than a forward reference. No application code reads or writes these tables
until Phase 9 -- see ADR-D1 (three-level hierarchy) and P4 (capture must work
with zero configuration): `activities.work_package_id` is nullable and this
table is allowed to stay empty indefinitely.

`work_package_planned_items` is a child table, not a single quantity column
on work_packages, because one package spans multiple trades/units (e.g.
"Ground Floor" has plastering in sqm, concreting in m3, blockwork in sqm) --
see ADR-D4. Revision columns implement ADR-D5 (planned quantities are
revisable with history; a frozen DPR keeps the denominator that was in
effect on its date, never silently rewritten by a later variation order).

`completion_mode` (P6) governs how a work package's % is computed once
planning data exists:
    NONE      - no plan entered; cumulative quantities only, no %
    QUANTITY  - planned_items exist; % = sum(done) / sum(planned), per line
    MILESTONE - no quantities; N activities marked required; % = done / N
    MANUAL    - an engineer's stated estimate, stored as a labelled claim
V1 only ever writes MANUAL (ADR-D10) -- the other three exist in the enum now
so this column is never revisited when Phase 9 lands.

Revision ID: 0420
Revises: 0410
Create Date: 2026-07-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0420"
down_revision = "0410"
branch_labels = None
depends_on = None

# create_type=False: the type is created explicitly below via a guarded DO
# block (idempotent regardless of partial-apply history — see module
# docstring addendum), so SQLAlchemy must never attempt to (re)create it
# implicitly while emitting CREATE TABLE DDL for a column using this type.
_completion_mode = sa.Enum(
    "NONE",
    "QUANTITY",
    "MILESTONE",
    "MANUAL",
    name="work_package_completion_mode",
    create_type=False,
)
_work_package_status = sa.Enum(
    "NOT_STARTED",
    "IN_PROGRESS",
    "ON_HOLD",
    "COMPLETED",
    name="work_package_status",
    create_type=False,
)


def _create_enum_if_not_exists(bind, name: str, values: tuple[str, ...]) -> None:
    """Guarded CREATE TYPE — Postgres has no native `IF NOT EXISTS` for
    enums, so this catches the DuplicateObject error instead. Needed after a
    real production incident (2026-07-27): a deploy run partially applied
    this migration (this enum committed, table creation failed later in the
    same run), and `Enum.create(bind, checkfirst=True)`'s existence check did
    not reliably prevent every retry from re-attempting the CREATE TYPE and
    failing on it forever after. This is unconditionally safe to re-run."""
    values_sql = ", ".join(f"'{v}'" for v in values)
    bind.execute(
        sa.text(
            f"DO $$ BEGIN "
            f"CREATE TYPE {name} AS ENUM ({values_sql}); "
            f"EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    _create_enum_if_not_exists(
        bind, "work_package_completion_mode", ("NONE", "QUANTITY", "MILESTONE", "MANUAL")
    )
    _create_enum_if_not_exists(
        bind, "work_package_status", ("NOT_STARTED", "IN_PROGRESS", "ON_HOLD", "COMPLETED")
    )

    # Each table (and its indexes) is guarded independently too — a prior
    # partial run may have committed one table but not the other, and
    # `alembic upgrade head` must converge cleanly regardless of which
    # combination of these already exists.
    existing_tables = inspector.get_table_names()

    if "work_packages" not in existing_tables:
        _create_work_packages_table()
    if "work_package_planned_items" not in existing_tables:
        _create_work_package_planned_items_table()


def _create_work_packages_table() -> None:
    op.create_table(
        "work_packages",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "site_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "parent_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("work_packages.id", ondelete="CASCADE"),
            nullable=True,
        ),
        # Sequential per project, e.g. WP-001 -- reuse 0400's generator
        # convention (computed at insert time in the application layer, not
        # backfilled here since this table starts empty).
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "location_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("location_nodes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("assigned_user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("planned_start", sa.Date(), nullable=True),
        sa.Column("planned_end", sa.Date(), nullable=True),
        sa.Column("actual_start", sa.Date(), nullable=True),
        sa.Column("actual_end", sa.Date(), nullable=True),
        sa.Column(
            "status", _work_package_status, nullable=False, server_default="NOT_STARTED"
        ),
        sa.Column(
            "completion_mode", _completion_mode, nullable=False, server_default="NONE"
        ),
        # Only meaningful when completion_mode = MANUAL (P6) -- an engineer's
        # stated estimate, never silently recomputed once QUANTITY/MILESTONE
        # data exists for the same package (ADR-D10).
        sa.Column("manual_completion_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("project_id", "code", name="uq_work_package_project_code"),
    )
    op.create_index("ix_work_packages_project_id", "work_packages", ["project_id"])
    op.create_index("ix_work_packages_site_id", "work_packages", ["site_id"])
    op.create_index("ix_work_packages_parent_id", "work_packages", ["parent_id"])


def _create_work_package_planned_items_table() -> None:
    op.create_table(
        "work_package_planned_items",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "work_package_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("work_packages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("work_type", sa.String(), nullable=False),
        sa.Column(
            "unit_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("units_of_measure.id"),
            nullable=False,
        ),
        sa.Column("planned_quantity", sa.Numeric(14, 3), nullable=False),
        # ADR-D5: revisions are recorded, never overwritten in place, so a
        # frozen DPR can keep the denominator in effect on its date.
        sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "superseded_by_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("work_package_planned_items.id"),
            nullable=True,
        ),
        sa.Column("revision_reason", sa.String(), nullable=True),
        sa.Column("changed_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_work_package_planned_items_package_id",
        "work_package_planned_items",
        ["work_package_id"],
    )
    # Partial unique index: only one *current* (non-superseded) planned line
    # per work_type/unit combination on a package.
    op.create_index(
        "uq_work_package_planned_item_current",
        "work_package_planned_items",
        ["work_package_id", "work_type", "unit_id"],
        unique=True,
        postgresql_where=sa.text("superseded_by_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_work_package_planned_item_current", table_name="work_package_planned_items"
    )
    op.drop_index(
        "ix_work_package_planned_items_package_id", table_name="work_package_planned_items"
    )
    op.drop_table("work_package_planned_items")

    op.drop_index("ix_work_packages_parent_id", table_name="work_packages")
    op.drop_index("ix_work_packages_site_id", table_name="work_packages")
    op.drop_index("ix_work_packages_project_id", table_name="work_packages")
    op.drop_table("work_packages")

    _work_package_status.drop(op.get_bind(), checkfirst=True)
    _completion_mode.drop(op.get_bind(), checkfirst=True)
