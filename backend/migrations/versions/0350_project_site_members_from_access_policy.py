"""Add site_members + project_members.site_access_mode, backfill both from users.access_policy.

Phase 1 of retiring the JSONB `users.access_policy` column as the source of
truth for project/site authorization (see the project/site membership audit).
Today there are three disconnected mechanisms: `users.access_policy` (read by
REST/mobile auth), `project_members` (written by the dashboard's Project
Members tab, read by nothing), and `project_memberships`/`site_memberships`
(read by the WhatsApp assistant's context resolver, written by nothing — hence
every WhatsApp report logging project/site as "Unmapped"). This migration
makes `project_members` capable of representing everything `access_policy`
can express, and backfills it from the existing policies so no currently-
configured access is lost when `AuthorizationService` is repointed at it.

`site_access_mode` mirrors `AccessPolicy.siteAccess.mode` ("all_sites" |
"custom_sites") directly on `project_members`, rather than materializing
"all sites" as one `site_members` row per site — that would go stale the
moment a new site is added to the project. `site_members` only ever holds
rows for the `custom_sites` case, exactly like `access_policy.siteAccess
.siteIds` today.

Same philosophy as 0290 (units_of_measure): never abort mid-migration on
production data (a mid-migration abort leaves the deploy half-applied — the
health-check/rollback path in the deploy workflow only runs if migrations
succeed). Malformed or dangling references (project/site IDs in a policy
that no longer exist) are skipped and logged, not fatal.

Revision ID: 0350
Revises: 0340
Create Date: 2026-07-12
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0350"
down_revision = "0340"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_members",
        sa.Column(
            "site_access_mode",
            sa.String(),
            nullable=False,
            server_default="all_sites",
        ),
    )

    op.create_table(
        "site_members",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "site_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("site_id", "user_id", name="uq_site_member"),
    )
    op.create_index("ix_site_members_site_id", "site_members", ["site_id"])
    op.create_index("ix_site_members_user_id", "site_members", ["user_id"])

    conn = op.get_bind()
    users = conn.execute(
        sa.text(
            "SELECT id, organization_id, access_policy FROM users WHERE access_policy IS NOT NULL"
        )
    ).fetchall()

    for user_id, org_id, policy in users:
        if not isinstance(policy, dict):
            print(f"Migration 0350: skipping user {user_id} — access_policy is not an object")  # noqa: T201
            continue

        mode = policy.get("mode")

        if mode == "all_projects":
            project_ids = conn.execute(
                sa.text("SELECT id FROM projects WHERE organization_id = :org_id"),
                {"org_id": org_id},
            ).fetchall()
            for (project_id,) in project_ids:
                conn.execute(
                    sa.text(
                        "INSERT INTO project_members "
                        "(id, project_id, user_id, role, site_access_mode) "
                        "VALUES (:id, :project_id, :user_id, 'SITE_ENGINEER', 'all_sites') "
                        "ON CONFLICT (project_id, user_id) DO NOTHING"
                    ),
                    {"id": uuid.uuid4(), "project_id": project_id, "user_id": user_id},
                )
            continue

        if mode != "custom_projects":
            print(  # noqa: T201
                f"Migration 0350: skipping user {user_id} — unrecognized access_policy mode {mode!r}"
            )
            continue

        grants = policy.get("projects")
        if not isinstance(grants, list):
            continue

        for grant in grants:
            if not isinstance(grant, dict):
                continue
            project_id_raw = grant.get("projectId")
            try:
                project_id = uuid.UUID(str(project_id_raw))
            except (ValueError, TypeError, AttributeError):
                print(  # noqa: T201
                    f"Migration 0350: skipping malformed projectId {project_id_raw!r} for user {user_id}"
                )
                continue

            project_exists = conn.execute(
                sa.text(
                    "SELECT 1 FROM projects WHERE id = :project_id AND organization_id = :org_id"
                ),
                {"project_id": project_id, "org_id": org_id},
            ).scalar()
            if not project_exists:
                print(  # noqa: T201
                    f"Migration 0350: skipping dangling projectId {project_id} for user {user_id} "
                    "(not found in this user's organization)"
                )
                continue

            site_access = grant.get("siteAccess")
            site_mode = site_access.get("mode") if isinstance(site_access, dict) else None
            if site_mode not in ("all_sites", "custom_sites"):
                # Mirrors AccessPolicy/resolve_site_scope's own deny-by-default
                # fallback for malformed siteAccess: zero sites, not all sites.
                site_mode = "custom_sites"

            conn.execute(
                sa.text(
                    "INSERT INTO project_members "
                    "(id, project_id, user_id, role, site_access_mode) "
                    "VALUES (:id, :project_id, :user_id, 'SITE_ENGINEER', :site_access_mode) "
                    "ON CONFLICT (project_id, user_id) DO NOTHING"
                ),
                {
                    "id": uuid.uuid4(),
                    "project_id": project_id,
                    "user_id": user_id,
                    "site_access_mode": site_mode,
                },
            )
            # A project_members row may already have existed (e.g. added via
            # the dashboard's Project Members tab, defaulting to all_sites) --
            # only narrow it here if the policy explicitly says custom_sites,
            # never widen an existing explicit grant based on stale JSON.
            if site_mode == "custom_sites":
                conn.execute(
                    sa.text(
                        "UPDATE project_members SET site_access_mode = 'custom_sites' "
                        "WHERE project_id = :project_id AND user_id = :user_id"
                    ),
                    {"project_id": project_id, "user_id": user_id},
                )

            if site_mode != "custom_sites":
                continue

            site_ids_raw = site_access.get("siteIds", []) if isinstance(site_access, dict) else []
            if not isinstance(site_ids_raw, list):
                continue
            for site_id_raw in site_ids_raw:
                try:
                    site_id = uuid.UUID(str(site_id_raw))
                except (ValueError, TypeError, AttributeError):
                    print(  # noqa: T201
                        f"Migration 0350: skipping malformed siteId {site_id_raw!r} for user {user_id}"
                    )
                    continue
                site_exists = conn.execute(
                    sa.text("SELECT 1 FROM sites WHERE id = :site_id AND project_id = :project_id"),
                    {"site_id": site_id, "project_id": project_id},
                ).scalar()
                if not site_exists:
                    print(  # noqa: T201
                        f"Migration 0350: skipping dangling siteId {site_id} for user {user_id} "
                        f"(not found under project {project_id})"
                    )
                    continue
                conn.execute(
                    sa.text(
                        "INSERT INTO site_members (id, site_id, user_id) "
                        "VALUES (:id, :site_id, :user_id) "
                        "ON CONFLICT (site_id, user_id) DO NOTHING"
                    ),
                    {"id": uuid.uuid4(), "site_id": site_id, "user_id": user_id},
                )


def downgrade() -> None:
    op.drop_index("ix_site_members_user_id", table_name="site_members")
    op.drop_index("ix_site_members_site_id", table_name="site_members")
    op.drop_table("site_members")
    op.drop_column("project_members", "site_access_mode")
