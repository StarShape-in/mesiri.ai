"""Add occurred_date_source to material_receipts and material_usage (M8).

No date field exists anywhere upstream (CanonicalEvent/DraftAction never
carry one), so the Application layer defaults occurred_date to the
confirmation/execution date. Silently doing that without a provenance marker
would let a "50 bags arrived yesterday" report get silently misdated as
"today" with no way to tell real vs. assumed dates apart later. This column
makes that distinction queryable: 'inferred_at_confirmation' is what M8
always writes today; 'reported' is reserved for when Understanding actually
extracts a stated date (not yet — no upstream path produces it).

Revision ID: 0220
Revises: 0210
Create Date: 2026-07-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0220"
down_revision = "0210"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "material_receipts",
        sa.Column(
            "occurred_date_source",
            sa.String(),
            nullable=False,
            server_default="inferred_at_confirmation",
        ),
    )
    op.add_column(
        "material_usage",
        sa.Column(
            "occurred_date_source",
            sa.String(),
            nullable=False,
            server_default="inferred_at_confirmation",
        ),
    )


def downgrade() -> None:
    op.drop_column("material_usage", "occurred_date_source")
    op.drop_column("material_receipts", "occurred_date_source")
