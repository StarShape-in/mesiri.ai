"""Shared structured error contract (M0).

Every failure that crosses an architectural boundary is represented as a
:class:`MesiriError`. Raw provider / database / SDK exceptions must be mapped
into this contract *before* they cross a boundary (see the Infrastructure and
AI Provider boundaries in ``02_ownership_and_boundaries.md``).

Ownership: SHARED ARCHITECTURE — changes require both developers' approval.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCategory(str, Enum):
    """Coarse classification used for handling / observability decisions."""

    CONFIGURATION = "configuration"
    DEPENDENCY = "dependency"          # a required dependency is unavailable
    TIMEOUT = "timeout"               # connect / operation deadline exceeded
    VALIDATION = "validation"         # input failed contract validation
    SERIALIZATION = "serialization"   # (de)serialization failure
    PROVIDER = "provider"             # external provider returned an error
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    UNAVAILABLE = "unavailable"       # service intentionally not ready
    INTERNAL = "internal"             # unexpected / unclassified


class ErrorCode(str, Enum):
    """Stable, greppable error codes — part of the observable contract."""

    CONFIG_INVALID = "CONFIG_INVALID"
    CONFIG_MISSING = "CONFIG_MISSING"

    POSTGRES_UNAVAILABLE = "POSTGRES_UNAVAILABLE"
    REDIS_UNAVAILABLE = "REDIS_UNAVAILABLE"
    OBJECT_STORAGE_UNAVAILABLE = "OBJECT_STORAGE_UNAVAILABLE"

    CONNECT_TIMEOUT = "CONNECT_TIMEOUT"
    OPERATION_TIMEOUT = "OPERATION_TIMEOUT"

    SERIALIZATION_ERROR = "SERIALIZATION_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"

    PROVIDER_ERROR = "PROVIDER_ERROR"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_MALFORMED_OUTPUT = "PROVIDER_MALFORMED_OUTPUT"

    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    # -- M4 Context Foundation (additive; authoritative context resolution) --
    UNKNOWN_EXTERNAL_IDENTITY = "UNKNOWN_EXTERNAL_IDENTITY"
    USER_DISABLED = "USER_DISABLED"
    ORGANIZATION_DISABLED = "ORGANIZATION_DISABLED"
    MEMBERSHIP_NOT_FOUND = "MEMBERSHIP_NOT_FOUND"
    MEMBERSHIP_DISABLED = "MEMBERSHIP_DISABLED"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    SITE_NOT_FOUND = "SITE_NOT_FOUND"
    PROJECT_ACCESS_DENIED = "PROJECT_ACCESS_DENIED"
    SITE_ACCESS_DENIED = "SITE_ACCESS_DENIED"
    AMBIGUOUS_ORGANIZATION = "AMBIGUOUS_ORGANIZATION"
    AMBIGUOUS_PROJECT = "AMBIGUOUS_PROJECT"
    AMBIGUOUS_SITE = "AMBIGUOUS_SITE"
    PROJECT_SITE_MISMATCH = "PROJECT_SITE_MISMATCH"
    ACTIVE_CONTEXT_INVALID = "ACTIVE_CONTEXT_INVALID"
    ACTIVE_CONTEXT_EXPIRED = "ACTIVE_CONTEXT_EXPIRED"
    CONTEXT_UNRESOLVED = "CONTEXT_UNRESOLVED"


# Generic, non-leaking message safe to surface to end users / health endpoints.
_DEFAULT_USER_MESSAGE = "Something went wrong while processing your request."


class MesiriError(Exception):
    """The single error type that crosses module boundaries.

    Attributes mirror the M0 error contract exactly: ``error_code``,
    ``category``, ``retryable``, ``user_safe_message``, ``internal_message``,
    ``correlation_id``, ``details``.
    """

    def __init__(
        self,
        *,
        error_code: str,
        category: ErrorCategory,
        retryable: bool = False,
        user_safe_message: str = _DEFAULT_USER_MESSAGE,
        internal_message: str = "",
        correlation_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.error_code = str(error_code)
        self.category = category
        self.retryable = retryable
        self.user_safe_message = user_safe_message
        self.internal_message = internal_message or user_safe_message
        self.correlation_id = correlation_id
        self.details = details or {}
        super().__init__(f"[{self.error_code}] {self.internal_message}")

    def with_correlation(self, correlation_id: str | None) -> MesiriError:
        """Attach a correlation id if one is not already present."""
        if correlation_id and not self.correlation_id:
            self.correlation_id = correlation_id
        return self

    def to_dict(self) -> dict[str, Any]:
        """Full structured form — intended for structured logs, not end users."""
        return {
            "error_code": self.error_code,
            "category": self.category.value,
            "retryable": self.retryable,
            "user_safe_message": self.user_safe_message,
            "internal_message": self.internal_message,
            "correlation_id": self.correlation_id,
            "details": self.details,
        }

    def to_public_dict(self) -> dict[str, Any]:
        """Redacted form safe to return over the wire / on health endpoints."""
        return {
            "error_code": self.error_code,
            "category": self.category.value,
            "retryable": self.retryable,
            "message": self.user_safe_message,
            "correlation_id": self.correlation_id,
        }

    # -- Convenience constructors for common infrastructure failures ---------

    @classmethod
    def configuration(
        cls,
        internal_message: str,
        *,
        code: str = ErrorCode.CONFIG_INVALID.value,
        details: dict[str, Any] | None = None,
    ) -> MesiriError:
        return cls(
            error_code=code,
            category=ErrorCategory.CONFIGURATION,
            retryable=False,
            user_safe_message="The service is misconfigured.",
            internal_message=internal_message,
            details=details,
        )

    @classmethod
    def dependency_unavailable(
        cls,
        dependency: str,
        *,
        code: str,
        internal_message: str = "",
        correlation_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> MesiriError:
        return cls(
            error_code=code,
            category=ErrorCategory.DEPENDENCY,
            retryable=True,
            user_safe_message="A required service is temporarily unavailable.",
            internal_message=internal_message or f"{dependency} unavailable",
            correlation_id=correlation_id,
            details={**(details or {}), "dependency": dependency},
        )

    @classmethod
    def timeout(
        cls,
        operation: str,
        *,
        code: str = ErrorCode.OPERATION_TIMEOUT.value,
        correlation_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> MesiriError:
        return cls(
            error_code=code,
            category=ErrorCategory.TIMEOUT,
            retryable=True,
            user_safe_message="The request took too long. Please try again.",
            internal_message=f"timeout during {operation}",
            correlation_id=correlation_id,
            details={**(details or {}), "operation": operation},
        )
