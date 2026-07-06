"""Context resolver — converts M2/M3 outputs into ResolvedContext.v1.

Read-only orchestration over the three Context ports. Performs no workflow
selection, persistence, rules evaluation, or transport rendering.

Ownership: Context module (post-M3). Does not modify M2 or M3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from mesiri_contracts.assistant.confidence import ConfidenceLevel
from mesiri_contracts.assistant.normalized_message import NormalizedMessage
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.common.errors import MesiriError
from mesiri_contracts.context.enums import ContextAmbiguityField
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
    ActorContext,
    ContextAmbiguity,
    InteractionContext,
    ReplyBindingContext,
    ResolvedContext,
    ScopeContext,
    WorkflowContext,
)


@dataclass(slots=True)
class _ResolutionState:
    """Mutable accumulator while resolving one inbound journey."""

    ambiguities: list[ContextAmbiguity] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ContractContextResolver:
    """Resolve business context from a normalized inbound message and understanding."""

    def __init__(
        self,
        *,
        identity: IdentityLookupPort,
        scope: ScopeLookupPort,
        workflow_state: WorkflowStateReadPort,
    ) -> None:
        self._identity = identity
        self._scope = scope
        self._workflow_state = workflow_state

    async def resolve(
        self,
        message: NormalizedMessage,
        understanding: UnderstandingResult,
    ) -> ResolvedContext:
        state = _ResolutionState()
        correlation_id = message.correlation_id
        self._validate_correlation(message, understanding, state)

        identity_record = await self._resolve_actor(message, state)
        actor = self._build_actor(message, identity_record, state)
        reply = self._resolve_reply_binding(message)

        scope_record = await self._resolve_scope(
            message,
            identity_record,
            reply,
            correlation_id,
            state,
        )
        scope = self._build_scope(scope_record, state)

        workflow = await self._resolve_active_workflow(actor.user_id, correlation_id, state)
        interaction = await self._resolve_pending_interaction(actor.user_id, correlation_id, state)

        confidence = self._calculate_confidence(actor, scope, state)

        return ResolvedContext(
            correlation_id=correlation_id,
            source_message_id=message.message_id,
            actor=actor,
            scope=scope,
            workflow=workflow,
            interaction=interaction,
            reply=reply,
            confidence=confidence,
            ambiguities=state.ambiguities,
            warnings=state.warnings,
            resolved_at=datetime.now(tz=UTC),
        )

    def _validate_correlation(
        self,
        message: NormalizedMessage,
        understanding: UnderstandingResult,
        state: _ResolutionState,
    ) -> None:
        if message.correlation_id != understanding.correlation_id:
            state.ambiguities.append(
                ContextAmbiguity(
                    field=ContextAmbiguityField.CORRELATION,
                    reason="message and understanding correlation_id mismatch",
                    candidates=[message.correlation_id, understanding.correlation_id],
                )
            )
            state.warnings.append("correlation_id mismatch between M2 and M3 outputs")

    async def _resolve_actor(
        self,
        message: NormalizedMessage,
        state: _ResolutionState,
    ) -> IdentityRecord | None:
        try:
            return await self._identity.resolve_by_whatsapp(
                message.sender.wa_id,
                correlation_id=message.correlation_id,
            )
        except MesiriError as err:
            state.warnings.append(err.user_safe_message)
            state.ambiguities.append(
                ContextAmbiguity(
                    field=ContextAmbiguityField.USER,
                    reason="identity lookup failed",
                )
            )
            return None

    def _build_actor(
        self,
        message: NormalizedMessage,
        identity_record: IdentityRecord | None,
        state: _ResolutionState,
    ) -> ActorContext:
        if identity_record is None:
            state.ambiguities.append(
                ContextAmbiguity(
                    field=ContextAmbiguityField.USER,
                    reason="whatsapp number not registered",
                )
            )
            return ActorContext(whatsapp_wa_id=message.sender.wa_id)

        if identity_record.organization_id is None:
            state.ambiguities.append(
                ContextAmbiguity(
                    field=ContextAmbiguityField.ORGANIZATION,
                    reason="user has no organization assignment",
                )
            )

        return ActorContext(
            whatsapp_wa_id=message.sender.wa_id,
            user_id=identity_record.user_id,
            organization_id=identity_record.organization_id,
            role=identity_record.role,
            display_name=identity_record.display_name or message.sender.profile_name,
        )

    def _resolve_reply_binding(self, message: NormalizedMessage) -> ReplyBindingContext:
        replied_to = (
            message.reply_context.replied_to_message_id if message.reply_context else None
        )
        return ReplyBindingContext(
            replied_to_message_id=replied_to,
            binds_to_prior_journey=bool(replied_to),
        )

    async def _resolve_scope(
        self,
        message: NormalizedMessage,
        identity_record: IdentityRecord | None,
        reply: ReplyBindingContext,
        correlation_id: str,
        state: _ResolutionState,
    ) -> ScopeRecord | None:
        if identity_record is None:
            state.ambiguities.append(
                ContextAmbiguity(
                    field=ContextAmbiguityField.SCOPE,
                    reason="scope lookup skipped without resolved user",
                )
            )
            return None

        try:
            if reply.replied_to_message_id:
                record = await self._scope.resolve_by_reply(
                    reply.replied_to_message_id,
                    correlation_id=correlation_id,
                )
                if record is not None:
                    state.warnings.append("scope resolved via reply binding")
                    return record
                state.warnings.append(
                    f"reply scope not found for message {reply.replied_to_message_id}"
                )

            if identity_record.organization_id is None:
                return None

            return await self._scope.resolve_default_scope(
                identity_record.user_id,
                identity_record.organization_id,
                correlation_id=correlation_id,
            )
        except MesiriError as err:
            state.warnings.append(err.user_safe_message)
            state.ambiguities.append(
                ContextAmbiguity(
                    field=ContextAmbiguityField.SCOPE,
                    reason="scope lookup failed",
                )
            )
            return None

    def _build_scope(
        self,
        scope_record: ScopeRecord | None,
        state: _ResolutionState,
    ) -> ScopeContext:
        if scope_record is None:
            if not any(a.field == ContextAmbiguityField.SCOPE for a in state.ambiguities):
                state.ambiguities.append(
                    ContextAmbiguity(
                        field=ContextAmbiguityField.SCOPE,
                        reason="project and site could not be resolved",
                    )
                )
            return ScopeContext()

        if scope_record.project_id is None:
            state.ambiguities.append(
                ContextAmbiguity(
                    field=ContextAmbiguityField.PROJECT,
                    reason="project could not be resolved",
                )
            )

        if scope_record.project_id is not None and scope_record.site_id is None:
            state.ambiguities.append(
                ContextAmbiguity(
                    field=ContextAmbiguityField.SITE,
                    reason="site could not be resolved",
                )
            )

        return ScopeContext(
            project_id=scope_record.project_id,
            project_name=scope_record.project_name,
            site_id=scope_record.site_id,
            site_name=scope_record.site_name,
        )

    async def _resolve_active_workflow(
        self,
        user_id: str | None,
        correlation_id: str,
        state: _ResolutionState,
    ) -> WorkflowContext | None:
        if user_id is None:
            return None
        try:
            snapshot = await self._workflow_state.get_active_workflow(
                user_id,
                correlation_id=correlation_id,
            )
        except MesiriError as err:
            state.warnings.append(err.user_safe_message)
            state.ambiguities.append(
                ContextAmbiguity(
                    field=ContextAmbiguityField.WORKFLOW,
                    reason="active workflow lookup failed",
                )
            )
            return None

        if snapshot is None:
            return None
        return WorkflowContext(
            workflow_instance_id=snapshot.workflow_instance_id,
            workflow_kind=snapshot.workflow_kind,
            phase=snapshot.phase,
        )

    async def _resolve_pending_interaction(
        self,
        user_id: str | None,
        correlation_id: str,
        state: _ResolutionState,
    ) -> InteractionContext | None:
        if user_id is None:
            return None
        try:
            snapshot = await self._workflow_state.get_pending_interaction(
                user_id,
                correlation_id=correlation_id,
            )
        except MesiriError as err:
            state.warnings.append(err.user_safe_message)
            state.ambiguities.append(
                ContextAmbiguity(
                    field=ContextAmbiguityField.INTERACTION,
                    reason="pending interaction lookup failed",
                )
            )
            return None

        if snapshot is None:
            return None
        return InteractionContext(
            interaction_id=snapshot.interaction_id,
            kind=snapshot.kind,
            related_message_id=snapshot.related_message_id,
        )

    def _calculate_confidence(
        self,
        actor: ActorContext,
        scope: ScopeContext,
        state: _ResolutionState,
    ) -> ConfidenceLevel:
        if any(a.field == ContextAmbiguityField.CORRELATION for a in state.ambiguities):
            return ConfidenceLevel.LOW

        if actor.user_id is None:
            return ConfidenceLevel.LOW

        if actor.organization_id is None:
            return ConfidenceLevel.LOW

        if scope.project_id is None or scope.site_id is None:
            return ConfidenceLevel.LOW

        if state.ambiguities:
            return ConfidenceLevel.MEDIUM

        if state.warnings:
            return ConfidenceLevel.MEDIUM

        return ConfidenceLevel.HIGH
