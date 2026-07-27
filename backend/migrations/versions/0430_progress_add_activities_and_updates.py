"""Add activities, progress_updates, site_issues, progress_attachments.

The V1 core of the Daily Reporting module
(docs/execution/DAILY_REPORTING_PLAN.md). Implements the three-level
hierarchy from ADR-D1:

    Work Package (0420, planning, lives months)
        -> Activity (this migration, execution, lives a day)
            -> Progress Update (this migration, timeline, lives a moment,
                                 APPEND ONLY -- see P1)

An Activity's `work_package_id` and `location_id` are NULLABLE (P4): a site
engineer must be able to file a useful report with no Work Package register
and no Location tree configured. Both are backfillable from the dashboard
later without touching the activity's own quantities.

`activity_links` (ADR-D2/P3) is the *only* way this module references
another module's records (attendance, material movements, equipment events,
expenses) -- deliberately no FK, since it points across domain boundaries the
application layer resolves, and deliberately no write path back into those
tables. Daily Reporting is never a second writer into another module's
ledger.

`activity_corrections` (ADR-D14) is the audit trail for header-field edits.
It exists precisely so a "quantity is 180 not 150" correction does NOT get
implemented as an edit to a progress_updates row -- those stay append-only
per P1. A correction mutates the Activity row and is audited here instead.

`progress_updates.supersedes_id` lets a correction to a *timeline* fact (not
a header fact) append a new row that supersedes an earlier one, rather than
editing it in place -- same append-only guarantee, applied to the update
itself rather than to the activity.

`site_issues` gets its own table rather than being an update_kind on
progress_updates because it has a lifecycle (open -> assigned -> resolved)
an append-only update cannot express.

`progress_attachments` mirrors expense_attachments' shape exactly (evidence
pattern reuse) with two additions: `ai_caption` is a separate column from
`caption` because the reporter's own caption is a fact and an AI-generated
one is an insight -- PRD principle 3 (strict facts/insights boundary) is
enforced at the schema level here, not left to rendering discipline.

Revision ID: 0430
Revises: 0420
Create Date: 2026-07-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0430"
down_revision = "0420"
branch_labels = None
depends_on = None

_activity_status = sa.Enum(
    "PLANNED", "IN_PROGRESS", "COMPLETED", "STOPPED", name="activity_status"
)
_measurement_type = sa.Enum("ACHIEVED", "CUMULATIVE", name="activity_measurement_type")
_linked_type = sa.Enum(
    "ATTENDANCE", "MATERIAL_MOVEMENT", "EQUIPMENT_EVENT", "EXPENSE", name="activity_linked_type"
)
_update_kind = sa.Enum(
    "STARTED", "PROGRESS", "PAUSED", "RESUMED", "COMPLETED", "NOTE", name="progress_update_kind"
)
_issue_type = sa.Enum(
    "WEATHER",
    "MATERIAL_SHORTAGE",
    "LABOUR_SHORTAGE",
    "DRAWING_PENDING",
    "EQUIPMENT_BREAKDOWN",
    "INSPECTION_WAITING",
    "ACCESS",
    "OTHER",
    name="site_issue_type",
)
_issue_severity = sa.Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="site_issue_severity")
_issue_status = sa.Enum(
    "OPEN", "ACKNOWLEDGED", "RESOLVED", "WONT_FIX", name="site_issue_status"
)
_attachment_parent_type = sa.Enum(
    "ACTIVITY", "PROGRESS_UPDATE", "SITE_ISSUE", name="progress_attachment_parent_type"
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (
        _activity_status,
        _measurement_type,
        _linked_type,
        _update_kind,
        _issue_type,
        _issue_severity,
        _issue_status,
        _attachment_parent_type,
    ):
        enum.create(bind, checkfirst=True)

    # -- activities ---------------------------------------------------------
    op.create_table(
        "activities",
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
            "site_id", sa.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
        ),
        # Nullable: P4 -- capture must work with zero Work Package/Location
        # configuration. Backfillable from the dashboard later.
        sa.Column(
            "work_package_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("work_packages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "location_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("location_nodes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Free text in V1 -- open decision #4 in the plan (promote to a
        # reference table once real usage shows the vocabulary is stable).
        sa.Column("work_type", sa.String(), nullable=True),
        sa.Column("activity_date", sa.Date(), nullable=False),
        sa.Column("started_at", sa.Time(), nullable=True),
        sa.Column("ended_at", sa.Time(), nullable=True),
        sa.Column("status", _activity_status, nullable=False, server_default="PLANNED"),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("contractor", sa.String(), nullable=True),
        sa.Column("reported_by_user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="whatsapp"),
        sa.Column("correlation_id", sa.String(), nullable=True),
        # ADR-D15: undo is a soft delete, never a hard delete, and only
        # available before a DPR version has frozen this activity (P7).
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index("ix_activities_org_project", "activities", ["organization_id", "project_id"])
    op.create_index("ix_activities_site_id", "activities", ["site_id"])
    op.create_index("ix_activities_work_package_id", "activities", ["work_package_id"])
    op.create_index("ix_activities_location_id", "activities", ["location_id"])
    op.create_index("ix_activities_activity_date", "activities", ["activity_date"])
    # "Find today's open activity for this reporter/site" -- the resolution
    # query behind activity_continuation (P10, resolve_activity.py).
    op.create_index(
        "ix_activities_open_lookup",
        "activities",
        ["site_id", "reported_by_user_id", "activity_date", "status"],
    )

    # -- activity_quantities --------------------------------------------------
    op.create_table(
        "activity_quantities",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "activity_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("work_type", sa.String(), nullable=True),
        sa.Column(
            "unit_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("units_of_measure.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("measurement_type", _measurement_type, nullable=False, server_default="ACHIEVED"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_activity_quantities_activity_id", "activity_quantities", ["activity_id"]
    )

    # -- activity_links (ADR-D2/P3: references only, no write path back) ----
    op.create_table(
        "activity_links",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "activity_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("linked_type", _linked_type, nullable=False),
        # No FK -- polymorphic across domain boundaries this module must not
        # depend on structurally. Resolved in the application layer.
        sa.Column("linked_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_activity_links_activity_id", "activity_links", ["activity_id"])
    op.create_index(
        "ix_activity_links_linked", "activity_links", ["linked_type", "linked_id"]
    )

    # -- activity_corrections (ADR-D14: header edits, audited, never a
    #    progress_updates edit) --------------------------------------------
    op.create_table(
        "activity_corrections",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "activity_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(), nullable=False),
        sa.Column("old_value", JSONB, nullable=True),
        sa.Column("new_value", JSONB, nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column(
            "corrected_by_user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_activity_corrections_activity_id", "activity_corrections", ["activity_id"]
    )

    # -- progress_updates (APPEND ONLY -- P1) --------------------------------
    op.create_table(
        "progress_updates",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "activity_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("update_kind", _update_kind, nullable=False),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("unit_id", sa.UUID(as_uuid=True), sa.ForeignKey("units_of_measure.id"), nullable=True),
        # A correction to a timeline fact appends a new row referencing the
        # one it supersedes -- it never edits the old row (P1).
        sa.Column(
            "supersedes_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("progress_updates.id"),
            nullable=True,
        ),
        sa.Column(
            "reported_by_user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("source", sa.String(), nullable=False, server_default="whatsapp"),
        sa.Column("correlation_id", sa.String(), nullable=True),
        # ADR-D15: same-session undo of an update the reporter just sent is a
        # soft delete, never a hard delete or an edit.
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_progress_updates_activity_id", "progress_updates", ["activity_id"]
    )
    op.create_index(
        "ix_progress_updates_occurred_at", "progress_updates", ["occurred_at"]
    )

    # -- site_issues ----------------------------------------------------------
    op.create_table(
        "site_issues",
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
            "site_id", sa.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
        ),
        # Nullable -- a blocker (e.g. "rain started") can precede any specific
        # activity, or apply to the whole site.
        sa.Column(
            "activity_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "work_package_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("work_packages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "location_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("location_nodes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("issue_type", _issue_type, nullable=False),
        sa.Column("severity", _issue_severity, nullable=False, server_default="MEDIUM"),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("delay_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", _issue_status, nullable=False, server_default="OPEN"),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("assigned_user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "reported_by_user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("correlation_id", sa.String(), nullable=True),
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
    )
    op.create_index("ix_site_issues_org_project", "site_issues", ["organization_id", "project_id"])
    op.create_index("ix_site_issues_site_id", "site_issues", ["site_id"])
    op.create_index("ix_site_issues_activity_id", "site_issues", ["activity_id"])
    op.create_index("ix_site_issues_status", "site_issues", ["status"])

    # -- progress_attachments (evidence -- mirrors expense_attachments) ------
    op.create_table(
        "progress_attachments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("parent_type", _attachment_parent_type, nullable=False),
        # No FK -- parent_type discriminates which table parent_id belongs to;
        # same polymorphic shape as activity_links, resolved in the application
        # layer.
        sa.Column("parent_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("media_object_key", sa.String(), nullable=False),
        sa.Column("attachment_type", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=True),
        # The REPORTER's own caption -- a fact.
        sa.Column("caption", sa.Text(), nullable=True),
        # AI-generated -- an insight. Never merged into `caption` (PRD
        # principle 3 / plan §1A.1(3)).
        sa.Column("ai_caption", sa.Text(), nullable=True),
        # BEFORE/AFTER/GENERAL -- open decision #8 in the plan; nullable
        # string rather than an enum until that decision lands, since it is
        # cheap to promote later and premature to lock in now.
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gps_lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("gps_lon", sa.Numeric(9, 6), nullable=True),
        sa.Column(
            "uploaded_by_user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_progress_attachments_parent", "progress_attachments", ["parent_type", "parent_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_progress_attachments_parent", table_name="progress_attachments")
    op.drop_table("progress_attachments")

    op.drop_index("ix_site_issues_status", table_name="site_issues")
    op.drop_index("ix_site_issues_activity_id", table_name="site_issues")
    op.drop_index("ix_site_issues_site_id", table_name="site_issues")
    op.drop_index("ix_site_issues_org_project", table_name="site_issues")
    op.drop_table("site_issues")

    op.drop_index("ix_progress_updates_occurred_at", table_name="progress_updates")
    op.drop_index("ix_progress_updates_activity_id", table_name="progress_updates")
    op.drop_table("progress_updates")

    op.drop_index("ix_activity_corrections_activity_id", table_name="activity_corrections")
    op.drop_table("activity_corrections")

    op.drop_index("ix_activity_links_linked", table_name="activity_links")
    op.drop_index("ix_activity_links_activity_id", table_name="activity_links")
    op.drop_table("activity_links")

    op.drop_index("ix_activity_quantities_activity_id", table_name="activity_quantities")
    op.drop_table("activity_quantities")

    op.drop_index("ix_activities_open_lookup", table_name="activities")
    op.drop_index("ix_activities_activity_date", table_name="activities")
    op.drop_index("ix_activities_location_id", table_name="activities")
    op.drop_index("ix_activities_work_package_id", table_name="activities")
    op.drop_index("ix_activities_site_id", table_name="activities")
    op.drop_index("ix_activities_org_project", table_name="activities")
    op.drop_table("activities")

    bind = op.get_bind()
    for enum in (
        _attachment_parent_type,
        _issue_status,
        _issue_severity,
        _issue_type,
        _update_kind,
        _linked_type,
        _measurement_type,
        _activity_status,
    ):
        enum.drop(bind, checkfirst=True)
