"""PostgreSQL-backed implementations of the M4 context ports.

Authoritative context lives here. Every project/site query is tenant-scoped by
``organization_id`` (and authorization-scoped by ``user_id`` for the
``get_authorized_*`` / ``find_authorized_*`` methods) so no query can ever leak
across organizations. Raw driver exceptions are mapped to the shared error
contract by the M1 infrastructure boundary (``map_postgres_error``).

SQL lives ONLY in this module — the resolver/orchestration never sees it. These
adapters take a SQLAlchemy ``AsyncEngine`` directly so M4 stays self-contained
without modifying the M1 ``PostgresDatabase`` facade.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from mesiri.infrastructure.errors import map_postgres_error

from .models import (
    ContextPreferences,
    ExternalIdentity,
    Membership,
    Organization,
    Project,
    Site,
    User,
)

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.ext.asyncio import AsyncEngine


class _EngineMixin:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def _rows(self, sql: str, params: dict[str, Any]) -> list[Any]:
        from sqlalchemy import text

        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                return list(result.mappings().all())
        except Exception as exc:  # noqa: BLE001
            raise map_postgres_error(exc) from exc

    async def _row(self, sql: str, params: dict[str, Any]) -> Any | None:
        rows = await self._rows(sql, params)
        return rows[0] if rows else None


def _digits(value: str) -> str:
    """Phone numbers as digits only. Mirrors ``_digits`` in backend/postgres/actor.py."""
    return re.sub(r"\D", "", value or "")


class PostgresExternalIdentityRepository(_EngineMixin):
    async def find_identity(
        self, *, provider: str, external_subject: str
    ) -> ExternalIdentity | None:
        # WhatsApp subjects are phone numbers written inconsistently: Meta sends
        # bare digits ("919876543210") while `external_identities.external_subject`
        # is projected verbatim from `users.whatsapp_number`, which an admin may
        # have typed as "+91 98765 43210". An exact match silently misses, and the
        # caller reports UNKNOWN_EXTERNAL_IDENTITY for a user who plainly exists.
        # Compare on digits, as the identity gate (actor.py) already does.
        #
        # This cannot use ix_external_identities_* — add a functional index on
        # regexp_replace(external_subject, '\D', '', 'g') if this table ever grows
        # past a trivial size.
        row = await self._row(
            "SELECT provider, external_subject, user_id FROM external_identities "
            "WHERE provider = :p AND regexp_replace(external_subject, '\\D', '', 'g') = :s",
            {"p": provider, "s": _digits(external_subject)},
        )
        if row is None:
            return None
        return ExternalIdentity(row["provider"], row["external_subject"], row["user_id"])

    async def get_user(self, user_id: str) -> User | None:
        row = await self._row(
            "SELECT id, is_active, locale, timezone FROM context_users WHERE id = :id",
            {"id": user_id},
        )
        if row is None:
            return None
        return User(row["id"], bool(row["is_active"]), row["locale"], row["timezone"])


class PostgresMembershipRepository(_EngineMixin):
    async def get_organization(self, organization_id: str) -> Organization | None:
        row = await self._row(
            "SELECT id, is_active FROM context_organizations WHERE id = :id",
            {"id": organization_id},
        )
        if row is None:
            return None
        return Organization(row["id"], bool(row["is_active"]))

    async def list_active_memberships(self, user_id: str) -> list[Membership]:
        rows = await self._rows(
            "SELECT m.id, m.organization_id, m.user_id, m.is_active "
            "FROM organization_memberships m "
            "JOIN context_organizations o ON o.id = m.organization_id "
            "WHERE m.user_id = :u AND m.is_active = true AND o.is_active = true "
            "ORDER BY m.organization_id",
            {"u": user_id},
        )
        return [
            Membership(r["id"], r["organization_id"], r["user_id"], bool(r["is_active"]))
            for r in rows
        ]


class PostgresRolePermissionRepository(_EngineMixin):
    async def role_ids_for_membership(self, membership_id: str) -> list[str]:
        rows = await self._rows(
            "SELECT role_id FROM membership_roles WHERE membership_id = :m ORDER BY role_id",
            {"m": membership_id},
        )
        return [r["role_id"] for r in rows]

    async def permissions_for_membership(self, membership_id: str) -> list[str]:
        rows = await self._rows(
            "SELECT DISTINCT p.code FROM membership_roles mr "
            "JOIN role_permissions rp ON rp.role_id = mr.role_id "
            "JOIN permissions p ON p.id = rp.permission_id "
            "WHERE mr.membership_id = :m ORDER BY p.code",
            {"m": membership_id},
        )
        return [r["code"] for r in rows]


def _project(r: Any) -> Project:
    return Project(r["id"], r["organization_id"], r["name"], bool(r["is_active"]))


def _site(r: Any) -> Site:
    return Site(r["id"], r["project_id"], r["organization_id"], r["name"], bool(r["is_active"]))


# A user is authorized for a project via a direct project_membership, (site
# membership implies its project), OR context_users.is_org_wide -- a live
# standing bypass (ADMIN role or access_policy.mode == "all_projects", see
# identity_projection.py's _project_user/_project_membership) that must
# cover every project in the org, including ones created after the grant.
# Checking it here rather than relying solely on the project_memberships
# snapshot means a brand-new project is visible to an org-wide user the
# moment its context_projects row is projected, with no membership resync
# needed. Tenant-scoped by organization_id everywhere.
_AUTHORIZED_PROJECT_IDS = (
    "SELECT p.id FROM context_projects p WHERE p.organization_id = :org AND p.is_active = true AND ("
    "  p.id IN (SELECT project_id FROM project_memberships WHERE user_id = :u)"
    "  OR p.id IN (SELECT s.project_id FROM site_memberships sm "
    "              JOIN context_sites s ON s.id = sm.site_id WHERE sm.user_id = :u)"
    "  OR EXISTS (SELECT 1 FROM context_users cu WHERE cu.id = :u AND cu.is_org_wide = true)"
    ")"
)


class PostgresProjectRepository(_EngineMixin):
    async def get_authorized_project(
        self, *, organization_id: str, user_id: str, project_id: str
    ) -> Project | None:
        row = await self._row(
            "SELECT id, organization_id, name, is_active FROM context_projects "
            f"WHERE id = :pid AND id IN ({_AUTHORIZED_PROJECT_IDS})",
            {"pid": project_id, "org": organization_id, "u": user_id},
        )
        return _project(row) if row else None

    async def find_authorized_projects_by_name(
        self, *, organization_id: str, user_id: str, name: str
    ) -> list[Project]:
        rows = await self._rows(
            "SELECT id, organization_id, name, is_active FROM context_projects "
            f"WHERE name ILIKE '%' || :name || '%' AND id IN ({_AUTHORIZED_PROJECT_IDS}) ORDER BY id",
            {"name": name.strip(), "org": organization_id, "u": user_id},
        )
        return [_project(r) for r in rows]

    async def list_authorized_projects(
        self, *, organization_id: str, user_id: str
    ) -> list[Project]:
        rows = await self._rows(
            "SELECT id, organization_id, name, is_active FROM context_projects "
            f"WHERE id IN ({_AUTHORIZED_PROJECT_IDS}) ORDER BY id",
            {"org": organization_id, "u": user_id},
        )
        return [_project(r) for r in rows]

    async def get_project_in_org(self, *, organization_id: str, project_id: str) -> Project | None:
        row = await self._row(
            "SELECT id, organization_id, name, is_active FROM context_projects "
            "WHERE id = :pid AND organization_id = :org AND is_active = true",
            {"pid": project_id, "org": organization_id},
        )
        return _project(row) if row else None


class PostgresSiteRepository(_EngineMixin):
    async def get_authorized_site(
        self, *, organization_id: str, user_id: str, site_id: str
    ) -> Site | None:
        row = await self._row(
            "SELECT s.id, s.project_id, s.organization_id, s.name, s.is_active FROM context_sites s "
            "WHERE s.id = :sid AND s.organization_id = :org AND s.is_active = true AND ("
            "  s.id IN (SELECT site_id FROM site_memberships WHERE user_id = :u)"
            f"  OR s.project_id IN ({_AUTHORIZED_PROJECT_IDS})"
            ")",
            {"sid": site_id, "org": organization_id, "u": user_id},
        )
        return _site(row) if row else None

    async def find_authorized_sites_by_name(
        self, *, organization_id: str, user_id: str, name: str, project_id: str | None = None
    ) -> list[Site]:
        clause = ""
        params: dict[str, Any] = {"name": name.strip(), "org": organization_id, "u": user_id}
        if project_id is not None:
            clause = " AND s.project_id = :pid"
            params["pid"] = project_id
        rows = await self._rows(
            "SELECT s.id, s.project_id, s.organization_id, s.name, s.is_active FROM context_sites s "
            "WHERE lower(s.name) = lower(:name) AND s.organization_id = :org "
            "AND s.is_active = true" + clause + " AND ("
            "  s.id IN (SELECT site_id FROM site_memberships WHERE user_id = :u)"
            f"  OR s.project_id IN ({_AUTHORIZED_PROJECT_IDS})"
            ") ORDER BY s.id",
            params,
        )
        return [_site(r) for r in rows]

    async def get_site_in_org(self, *, organization_id: str, site_id: str) -> Site | None:
        row = await self._row(
            "SELECT id, project_id, organization_id, name, is_active FROM context_sites "
            "WHERE id = :sid AND organization_id = :org AND is_active = true",
            {"sid": site_id, "org": organization_id},
        )
        return _site(row) if row else None


class PostgresContextPreferenceRepository(_EngineMixin):
    async def get_preferences(
        self, *, organization_id: str, user_id: str
    ) -> ContextPreferences | None:
        row = await self._row(
            "SELECT organization_id, user_id, default_project_id, default_site_id, locale, timezone "
            "FROM user_context_preferences WHERE organization_id = :org AND user_id = :u",
            {"org": organization_id, "u": user_id},
        )
        if row is None:
            return None
        return ContextPreferences(
            organization_id=row["organization_id"],
            user_id=row["user_id"],
            default_project_id=row["default_project_id"],
            default_site_id=row["default_site_id"],
            locale=row["locale"],
            timezone=row["timezone"],
        )


class PostgresReplyContextProvider(_EngineMixin):
    """Resolves a WhatsApp reply back to the context its target was recorded under.

    When an engineer long-presses a message and replies to it, that gesture is
    an explicit, unambiguous statement of which report they mean -- far
    stronger evidence than any NLP guess over "completed". `context_policy`
    already ranks REPLY_CONTEXT second only to an explicit in-message
    reference; until now the port behind it was `NullReplyContextProvider`, so
    the gesture was parsed at ingress and then discarded.

    `inbound_messages.dedup_key` holds the WhatsApp `wamid` verbatim (see
    runtime/dependencies.py, which sets it to `message.message_id`) and is
    UNIQUE, so this is an index lookup, not a scan. Retry rows suffix the key
    with `:retry:<correlation_id>` and therefore never match a real reply
    target -- correct, since a replayed admin retry is not something a user
    can long-press.

    Both joins are LEFT: a target message that was recorded before its project
    or site was resolved still yields whatever half is known, and the resolver
    validates each id against the sender's own authorizations afterwards
    (`_validated_candidate`). Tenancy is enforced by joining
    `context_organizations` rather than trusting the caller: `inbound_messages`
    stores the CANONICAL organization_id while this port is handed the CONTEXT
    one, so the join is both the translation and the tenant check.

    A reply can target EITHER of two messages, matched with the same query:
    the sender's own earlier message (`dedup_key`, as above) OR Mesiri's own
    reply to some earlier turn (`reply_wamid`, captured since migration 0452
    -- see runtime/inbound_journey.py's final "Send reply" step and
    channel/whatsapp/outbound.py's send_text_capturing_id). Replying to
    Mesiri's own "✅ Recorded." to reference or correct that record later is
    exactly the case `reply_wamid` closes -- `dedup_key` alone could never
    match it, since that column only ever holds an INBOUND message's id.

    Returns None when the target is unknown (expired retention, a message
    from before this feature, or a reply to an interactive list/button
    message -- those aren't reply_wamid-capturing yet, see migration 0452's
    docstring). None means "no opinion", which simply lets the next
    precedence level answer.
    """

    async def context_for_reply(
        self, *, organization_id: str, replied_to_message_id: str
    ) -> tuple[str | None, str | None] | None:
        row = await self._row(
            "SELECT cp.id AS project_id, cs.id AS site_id "
            "FROM inbound_messages im "
            "JOIN context_organizations co "
            "  ON co.canonical_organization_id = im.organization_id AND co.id = :org "
            "LEFT JOIN context_projects cp ON cp.canonical_project_id = im.project_id "
            "LEFT JOIN context_sites cs ON cs.canonical_site_id = im.site_id "
            "WHERE im.dedup_key = :wamid OR im.reply_wamid = :wamid "
            "ORDER BY im.received_at DESC "
            "LIMIT 1",
            {"org": organization_id, "wamid": replied_to_message_id},
        )
        if row is None:
            return None
        project_id = row["project_id"]
        site_id = row["site_id"]
        if project_id is None and site_id is None:
            # The target exists but carried no resolved scope -- that is not a
            # reply-context signal, and returning (None, None) would register
            # an empty candidate that outranks ACTIVE_CONTEXT for no reason.
            return None
        return (str(project_id) if project_id else None, str(site_id) if site_id else None)


class PostgresWorkflowContextProvider(_EngineMixin):
    """Scope inherited from the user's own in-flight workflow.

    A user mid-workflow ("which account?" / "reply YES to confirm") is
    demonstrably still talking about that workflow's project and site, so a
    follow-up message with no scope of its own should inherit it rather than
    fall back to whatever `active_context` last cached. This is the
    WORKFLOW_CONTEXT level of `context_policy`'s precedence chain, wired for
    the first time -- previously `NullWorkflowContextProvider`.

    Only genuinely open phases count. AWAITING_CONFIRMATION and
    COLLECTING_FIELDS are the two the runtime can actually resume
    (`get_awaiting_confirmation` / `get_awaiting_input`); a CONFIRMED or
    CANCELLED instance is finished and must not keep steering later messages.
    `ORDER BY updated_at DESC` is a tiebreak only -- the single-active
    invariant means there is normally at most one.

    project_id/site_id live inside the `state` JSONB (WorkflowStateV2), not as
    columns, so they are extracted with ->> and then mapped from canonical
    into context ids the same way as the reply provider above.
    """

    _OPEN_PHASES = ("awaiting_confirmation", "collecting_fields")

    async def active_workflow_context(
        self, *, organization_id: str, user_id: str
    ) -> tuple[str | None, str | None] | None:
        row = await self._row(
            "SELECT cp.id AS project_id, cs.id AS site_id "
            "FROM workflow_instances wi "
            "JOIN context_organizations co "
            "  ON co.canonical_organization_id = wi.organization_id AND co.id = :org "
            "JOIN context_users cu ON cu.canonical_user_id = wi.user_id AND cu.id = :usr "
            "LEFT JOIN context_projects cp "
            "  ON cp.canonical_project_id = NULLIF(wi.state->>'project_id', '')::uuid "
            "LEFT JOIN context_sites cs "
            "  ON cs.canonical_site_id = NULLIF(wi.state->>'site_id', '')::uuid "
            "WHERE wi.phase = ANY(:phases) "
            "ORDER BY wi.updated_at DESC "
            "LIMIT 1",
            {"org": organization_id, "usr": user_id, "phases": list(self._OPEN_PHASES)},
        )
        if row is None:
            return None
        project_id = row["project_id"]
        site_id = row["site_id"]
        if project_id is None and site_id is None:
            return None
        return (str(project_id) if project_id else None, str(site_id) if site_id else None)
