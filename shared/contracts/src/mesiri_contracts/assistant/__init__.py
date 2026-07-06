"""Assistant-facing shared contracts."""

from mesiri_contracts.assistant.context_enums import ContextConfidence, ContextSource
from mesiri_contracts.assistant.normalized_message import (
    MediaReference,
    NormalizedMessage,
    ReplyContext,
    SenderInfo,
)
from mesiri_contracts.assistant.resolved_context import (
    CONTRACT_VERSION as RESOLVED_CONTEXT_VERSION,
)
from mesiri_contracts.assistant.resolved_context import ResolvedContext

__all__ = [
    "MediaReference",
    "NormalizedMessage",
    "ReplyContext",
    "SenderInfo",
    "ResolvedContext",
    "ContextSource",
    "ContextConfidence",
    "RESOLVED_CONTEXT_VERSION",
]
