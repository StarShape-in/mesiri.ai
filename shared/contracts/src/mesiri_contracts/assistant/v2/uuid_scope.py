"""Canonical UUID string validation for v2 scope fields."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BeforeValidator


def validate_canonical_uuid(value: str) -> str:
    """Accept a UUID string; normalize to lowercase canonical form."""
    return str(UUID(value))


CanonicalUuid = Annotated[str, BeforeValidator(validate_canonical_uuid)]
