"""Identity → organization membership → roles/permissions resolution (M4).

This is the *authoritative* half of context resolution: it answers WHO is
speaking and WHICH organization they belong to, using PostgreSQL only. Nothing
here trusts AI output or Redis. The output ``Principal`` is the tenant-scoped
foundation every later stage (project/site authorization) builds on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mesiri_contracts.common.errors import MesiriError

from . import errors
from .ports import (
    ExternalIdentityRepository,
    OrganizationMembershipRepository,
    RolePermissionRepository,
)


@dataclass(frozen=True, slots=True)
class Principal:
    """Authoritative, tenant-scoped identity for the current message."""

    organization_id: str
    user_id: str
    membership_id: str
    role_ids: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    locale: str | None = None
    timezone: str | None = None


async def resolve_principal(
    *,
    provider: str,
    external_subject: str,
    identities: ExternalIdentityRepository,
    memberships: OrganizationMembershipRepository,
    roles: RolePermissionRepository,
) -> Principal:
    """Resolve the authoritative principal or raise a typed ``MesiriError``.

    Order: external identity -> active user -> single active membership ->
    active organization -> roles/permissions. Multiple active organizations is
    an explicit ambiguity (never silently chosen).
    """
    identity = await identities.find_identity(provider=provider, external_subject=external_subject)
    if identity is None:
        raise errors.unknown_external_identity(external_subject, provider=provider)

    user = await identities.get_user(identity.user_id)
    if user is None:
        raise errors.unknown_external_identity(external_subject, provider=provider)
    if not user.is_active:
        raise errors.user_disabled(user.user_id)

    active = await memberships.list_active_memberships(user.user_id)
    if not active:
        raise errors.membership_not_found(user.user_id)
    if len({m.organization_id for m in active}) > 1:
        raise errors.ambiguous_organization(
            user.user_id, sorted({m.organization_id for m in active})
        )

    membership = active[0]
    org = await memberships.get_organization(membership.organization_id)
    if org is None:
        raise errors.membership_not_found(user.user_id)
    if not org.is_active:
        raise errors.organization_disabled(org.organization_id)

    role_ids = await roles.role_ids_for_membership(membership.membership_id)
    permissions = await roles.permissions_for_membership(membership.membership_id)

    return Principal(
        organization_id=org.organization_id,
        user_id=user.user_id,
        membership_id=membership.membership_id,
        role_ids=role_ids,
        permissions=permissions,
        locale=user.locale,
        timezone=user.timezone,
    )


def is_context_error(error: MesiriError) -> bool:
    """True if ``error`` is one of the M4 identity/authorization codes."""
    from mesiri_contracts.common.errors import ErrorCode

    _M4 = {
        ErrorCode.UNKNOWN_EXTERNAL_IDENTITY.value,
        ErrorCode.USER_DISABLED.value,
        ErrorCode.ORGANIZATION_DISABLED.value,
        ErrorCode.MEMBERSHIP_NOT_FOUND.value,
        ErrorCode.MEMBERSHIP_DISABLED.value,
        ErrorCode.AMBIGUOUS_ORGANIZATION.value,
    }
    return error.error_code in _M4
