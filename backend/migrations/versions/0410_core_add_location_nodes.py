"""Add location_nodes — a shared, self-referential site-location tree.

Owned by `core`, not by the Daily Reporting module that first needs it (see
docs/execution/DAILY_REPORTING_PLAN.md ADR-D3/P9). Attendance, material
outflows, equipment events and progress activities all want to reference
"where on site this happened" — building it inside one module would mean
Labour or Materials reinventing the same tree within a month.

Deliberately NOT fixed Block/Floor/Room/Zone columns: road and linear
projects have chainage (km 12+400), tunnels have rings, plots have
boundaries. A self-referential tree with a free-text `level_label` per node
expresses all of these with one schema, instead of a column set that already
fails on the first non-building project.

`path` is a materialized, slash-separated ancestor id chain (root first,
this node last) maintained on write — chosen over a Postgres `ltree` column
to avoid adding an extension dependency for a single feature; revisit only if
subtree queries prove to be a real performance problem.

No FK consumers are added by this migration. Daily Reporting's `0420`/`0430`
add the first ones.

Revision ID: 0410
Revises: 0401
Create Date: 2026-07-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0410"
down_revision = "0401"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guarded: `alembic upgrade head` must converge cleanly even after a
    # deploy run that already committed this table but failed later in the
    # same invocation (see 0420's `_create_enum_if_not_exists` docstring for
    # the production incident this defends against across this whole batch
    # of migrations).
    if "location_nodes" in sa.inspect(op.get_bind()).get_table_names():
        return

    op.create_table(
        "location_nodes",
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
            sa.ForeignKey("location_nodes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        # Free text on purpose -- "Block", "Floor", "Zone", "Chainage", "Ring",
        # whatever the project's own vocabulary is. Never a fixed enum (P9).
        sa.Column("level_label", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        # Materialized ancestor chain, root-first, this node's own id last,
        # e.g. "<block-a-id>/<floor-2-id>". Maintained by the application
        # layer on insert/move, not recomputed live -- kept as a plain string
        # column rather than ltree to avoid a new Postgres extension for one
        # feature.
        sa.Column("path", sa.String(), nullable=False),
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
        sa.UniqueConstraint("parent_id", "name", name="uq_location_node_parent_name"),
    )
    op.create_index("ix_location_nodes_project_id", "location_nodes", ["project_id"])
    op.create_index("ix_location_nodes_site_id", "location_nodes", ["site_id"])
    op.create_index("ix_location_nodes_parent_id", "location_nodes", ["parent_id"])
    op.create_index("ix_location_nodes_path", "location_nodes", ["path"])


def downgrade() -> None:
    op.drop_index("ix_location_nodes_path", table_name="location_nodes")
    op.drop_index("ix_location_nodes_parent_id", table_name="location_nodes")
    op.drop_index("ix_location_nodes_site_id", table_name="location_nodes")
    op.drop_index("ix_location_nodes_project_id", table_name="location_nodes")
    op.drop_table("location_nodes")
