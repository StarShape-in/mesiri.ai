"""Normalize users.status to lowercase — repairs users locked out of WhatsApp.

The control panel's deactivate/reactivate wrote `body.status.capitalize()`,
producing "Active" for a user. Users are stored lowercase ("active"); only
organizations use the capitalized form. The WhatsApp assistant's own lookup
was `WHERE u.status = 'active'`, a case-sensitive comparison, so a
reactivated user matched nothing and the sender was told their number wasn't
recognized -- reactivating someone locked them out entirely.

The code fix makes reads case-insensitive and writes lowercase, so this only
has to repair rows already written in the wrong case. Idempotent: rows
already lowercase are untouched.

Deliberately scoped to `users`. `organizations.status` is conventionally
capitalized ("Active") and is compared as such elsewhere -- rewriting it
here would break the convention rather than fix anything.

Revision ID: 0368
Revises: 0367
Create Date: 2026-07-25
"""

from __future__ import annotations

from alembic import op

revision = "0368"
down_revision = "0367"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE users SET status = lower(status) "
        "WHERE status IS NOT NULL AND status <> lower(status)"
    )


def downgrade() -> None:
    # No downgrade: the capitalized form was the bug, and restoring it would
    # re-lock the affected users out of WhatsApp.
    pass
