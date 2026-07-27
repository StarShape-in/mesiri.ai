"""Add daily_reports, daily_report_versions, daily_report_sources.

Implements ADR-D6 and ADR-D9 (docs/execution/DAILY_REPORTING_PLAN.md): one
table with a `level` discriminator serves both the site-level DPR and the
project-level DPR, rather than two parallel tables duplicating the state
machine, versioning and freeze logic.

`daily_report_versions` is the frozen snapshot (P7): once a version is
approved, its `payload` JSONB is never mutated. A correction after approval
produces a NEW version row (via `supersedes_version_id`), never an edit to
the old one -- if a material movement is reversed tomorrow, yesterday's
already-approved DPR does not change; the change shows up as a new, visibly
different revision.

`daily_report_sources` implements P8's composition rule: a PROJECT-level
version is built FROM approved SITE-level versions, never independently
re-assembled from raw facts. It pins `site_version_id`, not the live
`daily_report_id` row, so a later site revision does not retroactively alter
an already-published project report. `site_version_id IS NULL` on a source
row means that site had not reported by cutoff -- the project DPR still
publishes, with that site recorded as NOT_REPORTED (P8); a missing site
report is the single most informative line on the page, not something the
rest of the project's reporting should be blocked on.

No application code writes to these tables yet -- this migration exists so
the schema is settled before Phase 6 (DPR assembly) starts, per the plan's
"schema first, both consumers build against it" implementation order.

Revision ID: 0440
Revises: 0430
Create Date: 2026-07-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0440"
down_revision = "0430"
branch_labels = None
depends_on = None

_dpr_level = sa.Enum("SITE", "PROJECT", name="daily_report_level")
_dpr_status = sa.Enum(
    "DRAFT", "IN_REVIEW", "APPROVED", "PUBLISHED", "NOT_REPORTED", name="daily_report_status"
)


def upgrade() -> None:
    bind = op.get_bind()
    _dpr_level.create(bind, checkfirst=True)
    _dpr_status.create(bind, checkfirst=True)

    op.create_table(
        "daily_reports",
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
        # NULL when level = PROJECT (a project-level report has no single site).
        sa.Column(
            "site_id", sa.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("level", _dpr_level, nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        # Sequential, e.g. DPR-001 -- reuse 0400's generator convention,
        # computed at insert time in the application layer.
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("status", _dpr_status, nullable=False, server_default="DRAFT"),
        sa.Column(
            "current_version_id",
            sa.UUID(as_uuid=True),
            nullable=True,
            # FK added after daily_report_versions exists (see below) --
            # avoids a circular forward reference within one migration.
        ),
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
        sa.UniqueConstraint(
            "project_id", "site_id", "report_date", "level", name="uq_daily_report_scope_date"
        ),
    )
    op.create_index("ix_daily_reports_project_id", "daily_reports", ["project_id"])
    op.create_index("ix_daily_reports_site_id", "daily_reports", ["site_id"])
    op.create_index("ix_daily_reports_report_date", "daily_reports", ["report_date"])

    op.create_table(
        "daily_report_versions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "daily_report_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("daily_reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        # FROZEN on approval (P7) -- the complete snapshot this version was
        # approved against. Never mutated after approved_at is set.
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("narrative_summary", sa.Text(), nullable=True),
        sa.Column("approved_by_user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "supersedes_version_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("daily_report_versions.id"),
            nullable=True,
        ),
        sa.Column("revision_reason", sa.String(), nullable=True),
        # Rendered document (ADR-D8 -- reuses channel/receipt/'s Playwright
        # pipeline); populated once the export step runs, nullable until then.
        sa.Column("rendered_object_key", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "daily_report_id", "version_no", name="uq_daily_report_version_no"
        ),
    )
    op.create_index(
        "ix_daily_report_versions_report_id", "daily_report_versions", ["daily_report_id"]
    )

    op.create_foreign_key(
        "fk_daily_reports_current_version",
        "daily_reports",
        "daily_report_versions",
        ["current_version_id"],
        ["id"],
    )

    op.create_table(
        "daily_report_sources",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_version_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("daily_report_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "site_daily_report_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("daily_reports.id"),
            nullable=False,
        ),
        # NULL means this site had not reported by cutoff -- recorded as
        # NOT_REPORTED (P8), the project DPR still publishes.
        sa.Column(
            "site_version_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("daily_report_versions.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "project_version_id", "site_daily_report_id", name="uq_daily_report_source"
        ),
    )
    op.create_index(
        "ix_daily_report_sources_project_version",
        "daily_report_sources",
        ["project_version_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_daily_report_sources_project_version", table_name="daily_report_sources"
    )
    op.drop_table("daily_report_sources")

    op.drop_constraint("fk_daily_reports_current_version", "daily_reports", type_="foreignkey")

    op.drop_index("ix_daily_report_versions_report_id", table_name="daily_report_versions")
    op.drop_table("daily_report_versions")

    op.drop_index("ix_daily_reports_report_date", table_name="daily_reports")
    op.drop_index("ix_daily_reports_site_id", table_name="daily_reports")
    op.drop_index("ix_daily_reports_project_id", table_name="daily_reports")
    op.drop_table("daily_reports")

    bind = op.get_bind()
    _dpr_status.drop(bind, checkfirst=True)
    _dpr_level.drop(bind, checkfirst=True)
