"""Context resolver runtime wiring and development diagnostics."""

from __future__ import annotations

import logging

from context.adapters import (
    FakeIdentityLookupPort,
    FakeScopeLookupPort,
    FakeWorkflowStateReadPort,
)
from context.contract_resolver import ContractContextResolver
from mesiri_contracts.context.resolved_context import ResolvedContext

logger = logging.getLogger(__name__)


def build_context_resolver() -> ContractContextResolver:
    """Construct the contract Context resolver from in-memory fake adapters."""
    return ContractContextResolver(
        identity=FakeIdentityLookupPort(),
        scope=FakeScopeLookupPort(),
        workflow_state=FakeWorkflowStateReadPort(),
    )


def log_resolved_context(context: ResolvedContext) -> None:
    """Log resolved context for development visibility (not user-facing)."""
    role = context.actor.role.value if context.actor.role else "unknown"
    logger.info(
        "ResolvedContext correlation_id=%s actor=%s organization=%s project=%s site=%s role=%s confidence=%s",
        context.correlation_id,
        context.actor.user_id or "unknown",
        context.actor.organization_id or "unknown",
        context.scope.project_id or "unknown",
        context.scope.site_id or "unknown",
        role,
        context.confidence.value,
    )
    if context.workflow is not None:
        logger.info(
            "ResolvedContext workflow=%s kind=%s phase=%s",
            context.workflow.workflow_instance_id,
            context.workflow.workflow_kind.value if context.workflow.workflow_kind else "unknown",
            context.workflow.phase.value,
        )
    if context.interaction is not None:
        logger.info(
            "ResolvedContext interaction=%s kind=%s",
            context.interaction.interaction_id,
            context.interaction.kind.value,
        )
    if context.ambiguities:
        logger.info(
            "ResolvedContext ambiguities=%s",
            [f"{a.field.value}:{a.reason}" for a in context.ambiguities],
        )
    if context.warnings:
        logger.info("ResolvedContext warnings=%s", context.warnings)
