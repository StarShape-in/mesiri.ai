"""M4 Context Foundation — resolve authoritative operating context.

Public surface: the ``ContextResolver`` (message -> ResolvedContext), the
``ContextSwitchService`` (active-context selection), the ports, and the
deterministic fakes. PostgreSQL is authoritative; Redis holds ephemeral active
context; AI understanding provides semantic references only.
"""

from __future__ import annotations

from .resolver import ContextDependencies, ContextResolver
from .service import ContextSwitchService

__all__ = [
    "ContextResolver",
    "ContextDependencies",
    "ContextSwitchService",
]
