"""M4 Context Foundation — resolve authoritative operating context.

Public surface: the ``ContextResolver`` (message -> ResolvedContext), the
``ContextSwitchService`` (active-context selection), the ports, and the
deterministic fakes. PostgreSQL is authoritative; Redis holds ephemeral active
context; AI understanding provides semantic references only.
"""

from __future__ import annotations

from context.contract_resolver import ContractContextResolver
from context.resolver import ContextDependencies, ContextResolver
from context.runtime import build_context_resolver, log_resolved_context
from context.service import ContextSwitchService

__all__ = [
    "ContextResolver",
    "ContractContextResolver",
    "ContextDependencies",
    "ContextSwitchService",
    "build_context_resolver",
    "log_resolved_context",
]
