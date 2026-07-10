"""M6.5 identity projection — idempotent control-plane → context layer sync."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .identity_bridge import (
    context_organization_id,
    context_project_id,
    context_site_id,
    context_user_id,
)

EntityType = Literal["organization", "user", "project", "site"]
WHATSAPP_PROVIDER = "whatsapp"


def _digits(value: str | None) -> str:
    """Phone numbers as digits only. Mirrors ``_digits`` in backend/postgres/actor.py."""
    return re.sub(r"\D", "", value or "")


@dataclass(slots=True)
class ReconcileReport:
    organizations: int = 0
    users: int = 0
    projects: int = 0
    sites: int = 0
    external_identities: int = 0
    memberships: int = 0
    errors: list[str] = field(default_factory=list)


def build_sync_engine() -> Engine:
    host = os.environ.get("MESIRI_POSTGRES__HOST", "localhost")
    port = os.environ.get("MESIRI_POSTGRES__PORT", "5432")
    user = os.environ.get("MESIRI_POSTGRES__USER", "mesiri")
    password = os.environ.get("MESIRI_POSTGRES__PASSWORD", "mesiri_local_dev")
    database = os.environ.get("MESIRI_POSTGRES__DATABASE", "mesiri")
    dsn = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"
    return create_engine(dsn, future=True)


class IdentityProjectionService:
    """One-way projection from control plane to context layer."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or build_sync_engine()

    def project_one(self, entity_type: EntityType, canonical_id: UUID) -> None:
        with self._engine.begin() as conn:
            if entity_type == "organization":
                self._project_organization(conn, canonical_id)
            elif entity_type == "user":
                self._project_user(conn, canonical_id)
            elif entity_type == "project":
                self._project_project(conn, canonical_id)
            elif entity_type == "site":
                self._project_site(conn, canonical_id)

    def reconcile_all(self) -> ReconcileReport:
        report = ReconcileReport()
        with self._engine.begin() as conn:
            org_rows = conn.execute(text("SELECT id, name, status FROM organizations")).mappings()
            for row in org_rows:
                try:
                    self._project_organization(conn, row["id"])
                    report.organizations += 1
                except Exception as exc:  # noqa: BLE001
                    report.errors.append(f"organization {row['id']}: {exc}")

            user_rows = conn.execute(
                text("SELECT id, full_name, organization_id, whatsapp_number, status FROM users")
            ).mappings()
            for row in user_rows:
                try:
                    self._project_user(conn, row["id"])
                    report.users += 1
                except Exception as exc:  # noqa: BLE001
                    report.errors.append(f"user {row['id']}: {exc}")

            project_rows = conn.execute(
                text("SELECT id, organization_id, name, status FROM projects")
            ).mappings()
            for row in project_rows:
                try:
                    self._project_project(conn, row["id"])
                    report.projects += 1
                except Exception as exc:  # noqa: BLE001
                    report.errors.append(f"project {row['id']}: {exc}")

            site_rows = conn.execute(
                text("SELECT id, organization_id, project_id, name, status FROM sites")
            ).mappings()
            for row in site_rows:
                try:
                    self._project_site(conn, row["id"])
                    report.sites += 1
                except Exception as exc:  # noqa: BLE001
                    report.errors.append(f"site {row['id']}: {exc}")

        return report

    def _project_organization(self, conn, canonical_id: UUID) -> None:
        row = (
            conn.execute(
                text("SELECT id, name, status FROM organizations WHERE id = :id"),
                {"id": canonical_id},
            )
            .mappings()
            .one()
        )
        ctx_id = context_organization_id(canonical_id)
        is_active = row["status"] == "Active"
        conn.execute(
            text(
                """
                INSERT INTO context_organizations (id, name, is_active, canonical_organization_id)
                VALUES (:id, :name, :is_active, :canonical_id)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    is_active = EXCLUDED.is_active,
                    canonical_organization_id = EXCLUDED.canonical_organization_id
                """
            ),
            {
                "id": ctx_id,
                "name": row["name"],
                "is_active": is_active,
                "canonical_id": canonical_id,
            },
        )

    def _project_user(self, conn, canonical_id: UUID) -> None:
        row = (
            conn.execute(
                text(
                    "SELECT id, full_name, organization_id, whatsapp_number, status "
                    "FROM users WHERE id = :id"
                ),
                {"id": canonical_id},
            )
            .mappings()
            .one()
        )
        ctx_id = context_user_id(canonical_id)
        is_active = row["status"] == "active"
        conn.execute(
            text(
                """
                INSERT INTO context_users (id, full_name, is_active, canonical_user_id)
                VALUES (:id, :name, :is_active, :canonical_id)
                ON CONFLICT (id) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    is_active = EXCLUDED.is_active,
                    canonical_user_id = EXCLUDED.canonical_user_id
                """
            ),
            {
                "id": ctx_id,
                "name": row["full_name"],
                "is_active": is_active,
                "canonical_id": canonical_id,
            },
        )
        if row["organization_id"] is not None:
            org_ctx = context_organization_id(row["organization_id"])
            membership_id = f"mbr_{ctx_id}_{org_ctx}"
            conn.execute(
                text(
                    """
                    INSERT INTO organization_memberships
                        (id, organization_id, user_id, is_active)
                    VALUES (:id, :org_id, :user_id, true)
                    ON CONFLICT (organization_id, user_id) DO UPDATE SET is_active = true
                    """
                ),
                {"id": membership_id, "org_id": org_ctx, "user_id": ctx_id},
            )
        # Store the subject as bare digits: Meta's inbound `wa_id` is digit-only,
        # while `users.whatsapp_number` may carry "+", spaces, or dashes. Writing
        # the raw value made lookups depend on how an admin typed the number, and
        # every lookup silently failed with UNKNOWN_EXTERNAL_IDENTITY as a result.
        digits = _digits(row["whatsapp_number"])
        if digits:
            ext_id = f"ext_{WHATSAPP_PROVIDER}_{digits}"
            conn.execute(
                text(
                    """
                    INSERT INTO external_identities (id, provider, external_subject, user_id)
                    VALUES (:id, :provider, :subject, :user_id)
                    ON CONFLICT (provider, external_subject) DO UPDATE SET user_id = EXCLUDED.user_id
                    """
                ),
                {
                    "id": ext_id,
                    "provider": WHATSAPP_PROVIDER,
                    "subject": digits,
                    "user_id": ctx_id,
                },
            )

    def _project_project(self, conn, canonical_id: UUID) -> None:
        row = (
            conn.execute(
                text("SELECT id, organization_id, name, status FROM projects WHERE id = :id"),
                {"id": canonical_id},
            )
            .mappings()
            .one()
        )
        ctx_id = context_project_id(canonical_id)
        org_ctx = context_organization_id(row["organization_id"])
        is_active = row["status"] == "on_track"
        conn.execute(
            text(
                """
                INSERT INTO context_projects
                    (id, organization_id, name, is_active, canonical_project_id)
                VALUES (:id, :org_id, :name, :is_active, :canonical_id)
                ON CONFLICT (id) DO UPDATE SET
                    organization_id = EXCLUDED.organization_id,
                    name = EXCLUDED.name,
                    is_active = EXCLUDED.is_active,
                    canonical_project_id = EXCLUDED.canonical_project_id
                """
            ),
            {
                "id": ctx_id,
                "org_id": org_ctx,
                "name": row["name"],
                "is_active": is_active,
                "canonical_id": canonical_id,
            },
        )

    def _project_site(self, conn, canonical_id: UUID) -> None:
        row = (
            conn.execute(
                text(
                    "SELECT id, organization_id, project_id, name, status FROM sites WHERE id = :id"
                ),
                {"id": canonical_id},
            )
            .mappings()
            .one()
        )
        ctx_id = context_site_id(canonical_id)
        org_ctx = context_organization_id(row["organization_id"])
        proj_ctx = context_project_id(row["project_id"])
        is_active = row["status"] == "active"
        conn.execute(
            text(
                """
                INSERT INTO context_sites
                    (id, project_id, organization_id, name, is_active, canonical_site_id)
                VALUES (:id, :proj_id, :org_id, :name, :is_active, :canonical_id)
                ON CONFLICT (id) DO UPDATE SET
                    project_id = EXCLUDED.project_id,
                    organization_id = EXCLUDED.organization_id,
                    name = EXCLUDED.name,
                    is_active = EXCLUDED.is_active,
                    canonical_site_id = EXCLUDED.canonical_site_id
                """
            ),
            {
                "id": ctx_id,
                "proj_id": proj_ctx,
                "org_id": org_ctx,
                "name": row["name"],
                "is_active": is_active,
                "canonical_id": canonical_id,
            },
        )
