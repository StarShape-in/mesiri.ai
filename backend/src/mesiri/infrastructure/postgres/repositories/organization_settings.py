"""PostgreSQL store for per-organization settings (migration 0364).

Reads fall back to the spec's default when no row exists — an org that has
never opened the control panel's settings page behaves exactly as it did
before the table existed (see domains/organizations/settings.py on why the
defaults are the real contract here).

Every method takes an externally-supplied connection and never commits,
matching the transaction-ownership rule the material repositories follow.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mesiri.domains.organizations import settings as settings_spec

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

_organization_settings = sa.Table(
    "organization_settings",
    sa.MetaData(),
    sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.UUID(as_uuid=True)),
    sa.Column("key", sa.String),
    sa.Column("value", JSONB),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    sa.Column("updated_by", sa.UUID(as_uuid=True)),
)


class PostgresOrganizationSettingsRepository:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def get(self, organization_id: uuid.UUID, key: str) -> Any:
        """The org's value for `key`, or the spec default when unset."""
        row = (
            await self._conn.execute(
                sa.select(_organization_settings.c.value).where(
                    _organization_settings.c.organization_id == organization_id,
                    _organization_settings.c.key == key,
                )
            )
        ).first()
        if row is None:
            return settings_spec.default_for(key)
        return row.value

    async def get_all(self, organization_id: uuid.UUID) -> dict[str, Any]:
        """Every known setting for the org, defaults filled in for unset keys.

        Returns all specs rather than only stored rows so the control panel
        renders a complete form on first load, with no special-casing for an
        org that has never saved anything.
        """
        rows = (
            await self._conn.execute(
                sa.select(
                    _organization_settings.c.key, _organization_settings.c.value
                ).where(_organization_settings.c.organization_id == organization_id)
            )
        ).all()
        stored = {row.key: row.value for row in rows}
        return {
            spec.key: stored.get(spec.key, spec.default)
            for spec in settings_spec.all_specs()
        }

    async def set(
        self,
        organization_id: uuid.UUID,
        key: str,
        value: Any,
        *,
        updated_by: uuid.UUID | None,
    ) -> Any:
        """Upsert one setting. Caller is responsible for having validated
        `value` against the spec (see settings.validate) — this only persists.
        """
        stmt = (
            pg_insert(_organization_settings)
            .values(
                id=uuid.uuid4(),
                organization_id=organization_id,
                key=key,
                value=value,
                updated_by=updated_by,
            )
            .on_conflict_do_update(
                constraint="uq_organization_settings_org_key",
                set_={
                    "value": value,
                    "updated_by": updated_by,
                    "updated_at": sa.text("now()"),
                },
            )
        )
        await self._conn.execute(stmt)
        return value
