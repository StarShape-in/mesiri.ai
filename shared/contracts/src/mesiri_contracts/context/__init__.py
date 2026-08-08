"""Context module port interfaces and enumerations.

Exports the ports, port-side DTOs, and enumerations used by the M4
ContextResolver and its adapters.

The nested ``ResolvedContext`` (and its sub-classes ``ActorContext``,
``ScopeContext``, etc.) that previously lived in this package has been
retired in Phase 0 T4.  The canonical M4 flat schema is:

    mesiri_contracts.assistant.resolved_context.ResolvedContext
"""

from mesiri_contracts.context.enums import (
    ContextAmbiguityField,
    InteractionKind,
    UserRole,
    WorkflowKind,
    WorkflowPhase,
)
from mesiri_contracts.context.ports import (
    ActiveWorkflowSnapshot,
    IdentityLookupPort,
    IdentityRecord,
    PendingInteractionSnapshot,
    ScopeLookupPort,
    ScopeRecord,
    WorkflowStateReadPort,
)

__all__ = [
    "ActiveWorkflowSnapshot",
    "ContextAmbiguityField",
    "IdentityLookupPort",
    "IdentityRecord",
    "InteractionKind",
    "PendingInteractionSnapshot",
    "ScopeLookupPort",
    "ScopeRecord",
    "UserRole",
    "WorkflowKind",
    "WorkflowPhase",
    "WorkflowStateReadPort",
]
