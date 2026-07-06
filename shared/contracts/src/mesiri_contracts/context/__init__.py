"""Context module shared contracts (ResolvedContext.v1 + read ports)."""

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
from mesiri_contracts.context.resolved_context import (
    CONTRACT_VERSION,
    ActorContext,
    ContextAmbiguity,
    InteractionContext,
    ReplyBindingContext,
    ResolvedContext,
    ScopeContext,
    WorkflowContext,
)

__all__ = [
    "CONTRACT_VERSION",
    "ActiveWorkflowSnapshot",
    "ActorContext",
    "ContextAmbiguity",
    "ContextAmbiguityField",
    "IdentityLookupPort",
    "IdentityRecord",
    "InteractionContext",
    "InteractionKind",
    "PendingInteractionSnapshot",
    "ReplyBindingContext",
    "ResolvedContext",
    "ScopeContext",
    "ScopeLookupPort",
    "ScopeRecord",
    "UserRole",
    "WorkflowContext",
    "WorkflowKind",
    "WorkflowPhase",
    "WorkflowStateReadPort",
]
