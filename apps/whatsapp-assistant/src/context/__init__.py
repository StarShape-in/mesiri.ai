"""M4 Context Foundation — resolve authoritative operating context.

Public surface: the ``ContextResolver`` (message -> ResolvedContext), the
``ContextSwitchService`` (active-context selection), the ports, and the
deterministic fakes. PostgreSQL is authoritative; Redis holds ephemeral active
context; AI understanding contributes semantic references only.

Phase 0 note: ``ContractContextResolver`` has been retired. The production path
now uses ``ContextResolver`` with real PostgreSQL adapters.
"""

from __future__ import annotations

from context.resolver import ContextDependencies, ContextResolver
from context.runtime import build_context_resolver, log_resolved_context
from context.service import ContextSwitchService

__all__ = [
    "ContextResolver",
    "ContextDependencies",
    "ContextSwitchService",
    "build_context_resolver",
    "log_resolved_context",
]
