"""Add context_users.is_org_wide -- a live, standing project-access bypass.

An ADMIN role or an access_policy.mode == "all_projects" grant is supposed to
see every project in the org, present and future, without an explicit
project_memberships row per project (the same live-bypass treatment
0350/6c13a08 already gave the control-plane `projects`/`project_members`
reads in backend/authorization/service.py and
whatsapp-assistant/src/backend/postgres/actor.py). The WhatsApp context
resolver's own authorization table (context/postgres_repositories.py's
_AUTHORIZED_PROJECT_IDS) was the one place that fix missed: it only ever
reads project_memberships, a snapshot IdentityProjectionService._project_membership
materializes at grant time. A project created *after* the grant has no
project_memberships row for that org-wide user, so PostgresProjectRepository
reports zero authorized projects and every WhatsApp report from that user
fails validation with "project is not resolved" -- exactly the class of bug
6c13a08 fixed everywhere else.

is_org_wide is set by identity_projection.py whenever a user's role or
access_policy is (re)projected, and _AUTHORIZED_PROJECT_IDS now ORs against
it directly, so a newly created project's context_projects row (written by
_project_project on every project create) is immediately visible to an
org-wide user without needing that user's own membership resynced.

Revision ID: 0364
Revises: 0363
Create Date: 2026-07-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0364"
down_revision = "0363"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "context_users",
        sa.Column("is_org_wide", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Backfill: every context_users row already ties back to its canonical
    # `users` row via canonical_user_id (see identity_projection.py). Without
    # this, an existing ADMIN/all_projects user stays is_org_wide = false
    # (the column default) until something happens to re-trigger their own
    # "user" or "membership" projection -- this makes the fix effective
    # immediately for everyone already granted the bypass, not just future
    # grants.
    op.execute(
        """
        UPDATE context_users cu
        SET is_org_wide = true
        FROM users u
        WHERE cu.canonical_user_id = u.id
          AND (
            upper(u.role) = 'ADMIN'
            OR (u.access_policy ->> 'mode') = 'all_projects'
          )
        """
    )


def downgrade() -> None:
    op.drop_column("context_users", "is_org_wide")
