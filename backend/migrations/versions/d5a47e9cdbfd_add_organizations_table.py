"""add organizations table

Revision ID: d5a47e9cdbfd
Revises: c4936d8bcaec
Create Date: 2026-07-05 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd5a47e9cdbfd'
down_revision: str | None = 'c4936d8bcaec'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'organizations',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('deployment_type', sa.String(), nullable=False),
        sa.Column('db_route', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False)
    )
    op.create_index('ix_organizations_name', 'organizations', ['name'], unique=False)

def downgrade() -> None:
    op.drop_index('ix_organizations_name', table_name='organizations')
    op.drop_table('organizations')
