"""M4 context-resolution error mapping.

Every context failure that crosses a boundary is a :class:`MesiriError` carrying
a stable M4 ``ErrorCode``. Raw PostgreSQL / Redis exceptions are mapped by the
infrastructure adapters (``mesiri.infrastructure.errors``) *before* they reach
here; this module only builds the domain-level context errors. Correlation ids
are pulled from the ambient tracing context so callers never pass them by hand.
"""

from __future__ import annotations

from typing import Any

from mesiri.observability import tracing
from mesiri_contracts.common.errors import ErrorCategory, ErrorCode, MesiriError


def _err(
    *,
    code: ErrorCode,
    category: ErrorCategory,
    user_message: str,
    internal: str,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> MesiriError:
    return MesiriError(
        error_code=code.value,
        category=category,
        retryable=retryable,
        user_safe_message=user_message,
        internal_message=internal,
        correlation_id=tracing.get_correlation_id(),
        details=details or {},
    )


def unknown_external_identity(external_subject: str, *, provider: str = "whatsapp") -> MesiriError:
    return _err(
        code=ErrorCode.UNKNOWN_EXTERNAL_IDENTITY,
        category=ErrorCategory.NOT_FOUND,
        user_message="We don't recognise this number yet. Please ask an admin to add you.",
        internal=f"no external identity for provider={provider} subject={external_subject}",
        details={"provider": provider},
    )


def user_disabled(user_id: str) -> MesiriError:
    return _err(
        code=ErrorCode.USER_DISABLED,
        category=ErrorCategory.CONFLICT,
        user_message="Your account is disabled. Please contact an admin.",
        internal=f"user {user_id} is disabled",
        details={"user_id": user_id},
    )


def organization_disabled(organization_id: str) -> MesiriError:
    return _err(
        code=ErrorCode.ORGANIZATION_DISABLED,
        category=ErrorCategory.CONFLICT,
        user_message="This organization is not active.",
        internal=f"organization {organization_id} is disabled",
        details={"organization_id": organization_id},
    )


def membership_not_found(user_id: str) -> MesiriError:
    return _err(
        code=ErrorCode.MEMBERSHIP_NOT_FOUND,
        category=ErrorCategory.NOT_FOUND,
        user_message="You are not a member of any active organization.",
        internal=f"no active membership for user {user_id}",
        details={"user_id": user_id},
    )


def membership_disabled(membership_id: str) -> MesiriError:
    return _err(
        code=ErrorCode.MEMBERSHIP_DISABLED,
        category=ErrorCategory.CONFLICT,
        user_message="Your membership is not active.",
        internal=f"membership {membership_id} is disabled",
        details={"membership_id": membership_id},
    )


def project_not_found(reference: str) -> MesiriError:
    return _err(
        code=ErrorCode.PROJECT_NOT_FOUND,
        category=ErrorCategory.NOT_FOUND,
        user_message=f"No project matched “{reference}”.",
        internal=f"no authorized project for reference={reference!r}",
        details={"reference": reference},
    )


def site_not_found(reference: str) -> MesiriError:
    return _err(
        code=ErrorCode.SITE_NOT_FOUND,
        category=ErrorCategory.NOT_FOUND,
        user_message=f"No site matched “{reference}”.",
        internal=f"no authorized site for reference={reference!r}",
        details={"reference": reference},
    )


def project_access_denied(organization_id: str, user_id: str, project_id: str) -> MesiriError:
    return _err(
        code=ErrorCode.PROJECT_ACCESS_DENIED,
        category=ErrorCategory.VALIDATION,
        user_message="You don't have access to that project.",
        internal=f"user {user_id} not authorized for project {project_id}",
        details={"organization_id": organization_id, "user_id": user_id, "project_id": project_id},
    )


def site_access_denied(organization_id: str, user_id: str, site_id: str) -> MesiriError:
    return _err(
        code=ErrorCode.SITE_ACCESS_DENIED,
        category=ErrorCategory.VALIDATION,
        user_message="You don't have access to that site.",
        internal=f"user {user_id} not authorized for site {site_id}",
        details={"organization_id": organization_id, "user_id": user_id, "site_id": site_id},
    )


def ambiguous_organization(user_id: str, organization_ids: list[str]) -> MesiriError:
    return _err(
        code=ErrorCode.AMBIGUOUS_ORGANIZATION,
        category=ErrorCategory.VALIDATION,
        user_message="You belong to more than one organization. Please specify which one.",
        internal=f"user {user_id} has multiple active organizations",
        details={"user_id": user_id, "organization_ids": organization_ids},
    )


def ambiguous_project(reference: str, project_ids: list[str]) -> MesiriError:
    return _err(
        code=ErrorCode.AMBIGUOUS_PROJECT,
        category=ErrorCategory.VALIDATION,
        user_message=f"“{reference}” matches more than one project. Which one?",
        internal=f"reference={reference!r} matched multiple projects",
        details={"reference": reference, "project_ids": project_ids},
    )


def ambiguous_site(reference: str, site_ids: list[str]) -> MesiriError:
    return _err(
        code=ErrorCode.AMBIGUOUS_SITE,
        category=ErrorCategory.VALIDATION,
        user_message=f"“{reference}” matches more than one site. Which one?",
        internal=f"reference={reference!r} matched multiple sites",
        details={"reference": reference, "site_ids": site_ids},
    )


def project_site_mismatch(project_id: str, site_id: str) -> MesiriError:
    return _err(
        code=ErrorCode.PROJECT_SITE_MISMATCH,
        category=ErrorCategory.VALIDATION,
        user_message="That site does not belong to that project.",
        internal=f"site {site_id} does not belong to project {project_id}",
        details={"project_id": project_id, "site_id": site_id},
    )


def active_context_invalid(reason: str) -> MesiriError:
    return _err(
        code=ErrorCode.ACTIVE_CONTEXT_INVALID,
        category=ErrorCategory.VALIDATION,
        user_message="Your active context is no longer valid.",
        internal=f"active context invalid: {reason}",
        details={"reason": reason},
    )


def active_context_expired() -> MesiriError:
    return _err(
        code=ErrorCode.ACTIVE_CONTEXT_EXPIRED,
        category=ErrorCategory.VALIDATION,
        user_message="Your active context has expired.",
        internal="active context expired",
    )


def context_unresolved(internal: str = "no context candidate resolved") -> MesiriError:
    return _err(
        code=ErrorCode.CONTEXT_UNRESOLVED,
        category=ErrorCategory.VALIDATION,
        user_message="I couldn't tell which project this belongs to. Please specify.",
        internal=internal,
    )
