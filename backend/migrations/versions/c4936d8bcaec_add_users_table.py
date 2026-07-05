"""Add users table

Revision ID: c4936d8bcaec
Revises: 0001_m1_infra_heartbeat
Create Date: 2026-07-05 11:34:51.302308
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'c4936d8bcaec'
down_revision = '0001_m1_infra_heartbeat'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('whatsapp_number', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False)
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_whatsapp_number', 'users', ['whatsapp_number'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_whatsapp_number', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
