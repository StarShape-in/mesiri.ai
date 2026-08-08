"""Add users.username and make users.email optional.

Until now every user needed a real email + password to exist at all --
fine for a dashboard-first signup, but a WhatsApp-created user (a site
engineer added by "add Rajesh, 9198765xxxxx, as site engineer") has neither:
WhatsApp text can supply a name and a phone number reliably, never a real
email address, and there is no form to type a password into.

**username** is the new second identifier a person can log into the
dashboard with, alongside email. For a WhatsApp-created user it is set to
their WhatsApp number's digits (already unique via ix_users_whatsapp_number,
so reusing it sidesteps inventing a separate slug/dedupe scheme). Nullable
and independently unique -- a dashboard-created user has no username unless
one is set later, same as a WhatsApp-created user has no email unless one
is added later.

**email** drops its NOT NULL. Its unique index already tolerates multiple
NULLs (Postgres treats NULL as distinct in a unique index), so no partial
index or migration of existing rows is needed -- every current row already
has a real email and is unaffected.

Application-level validation (not a DB constraint) requires at least one of
email/username at creation time; enforcing "at least one of two nullable
columns" as a CHECK constraint is possible but the two creation paths
(dashboard's users/router.py, WhatsApp's create_user workflow) already
guarantee it structurally -- one always sets email, the other always sets
username -- so the extra constraint would only catch a bug already caught
by every existing test of either path.

Revision ID: 0457
Revises: 0456
Create Date: 2026-07-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0457"
down_revision = "0456"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(), nullable=True))
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.alter_column("users", "email", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.alter_column("users", "email", existing_type=sa.String(), nullable=False)
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
