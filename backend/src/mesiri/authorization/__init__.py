"""Authorization package for access control and permission management.

Provides:
- AuthorizationContext: Request-scoped authorization state
- AuthorizationService: Resolution of user permissions and access scope
- AccessPolicy, ProjectAccessScope: Policy and scope models
"""

from .context import (
    AccessPolicy,
    AuthorizationContext,
    ProjectAccessScope,
)
from .service import AuthorizationService

__all__ = [
    "AccessPolicy",
    "AuthorizationContext",
    "ProjectAccessScope",
    "AuthorizationService",
]
