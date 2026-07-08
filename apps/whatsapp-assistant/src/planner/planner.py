"""Planner (M5) — reads a CanonicalEvent, returns a PlannerDecision.

Pure, deterministic router — no LLM, no I/O, no knowledge of LangGraph or any
specific graph (architecture rule #10: "Planner never imports a workflow
engine or a specific graph"). Mirrors how the canonicalization builder and
M3's ConfidencePolicy are pure functions over their inputs.
"""

from __future__ import annotations

import logging

from mesiri_contracts.assistant.canonical_event import (
    CanonicalEvent,
    CanonicalEventType,
    IntentCompleteness,
)
from mesiri_contracts.assistant.planner_decision import (
    PlannerDecision,
    PlannerDecisionType,
    PlannerPriority,
)

from .routing import WORKFLOW_KEY_BY_EVENT

logger = logging.getLogger(__name__)


class Planner:
    """Routes a CanonicalEvent to a PlannerDecision. Stateless — safe to share."""

    def decide(self, event: CanonicalEvent) -> PlannerDecision:
        if event.completeness is IntentCompleteness.ACTIONABLE:
            # .get(), never direct indexing: a future actionable CanonicalEventType
            # added without a matching routing-table entry must degrade safely
            # rather than crash the journey with an uncontrolled KeyError.
            workflow_key = WORKFLOW_KEY_BY_EVENT.get(event.event_type)
            if workflow_key is not None:
                decision_type = PlannerDecisionType.START_WORKFLOW
            else:
                logger.warning("planner.routing_gap event_type=%s", event.event_type.value)
                decision_type = PlannerDecisionType.DIRECT_REPLY
        elif event.event_type is CanonicalEventType.CLARIFICATION_REQUIRED:
            decision_type = PlannerDecisionType.CLARIFY
            workflow_key = None
        else:
            decision_type = PlannerDecisionType.DIRECT_REPLY
            workflow_key = None

        return PlannerDecision(
            correlation_id=event.correlation_id,
            source_message_id=event.source_message_id,
            causation_event_id=event.event_id,
            decision_type=decision_type,
            workflow_key=workflow_key,
            reason=event.event_type,
            priority=PlannerPriority.NORMAL,
            organization_id=event.organization_id,
            user_id=event.user_id,
            project_id=event.project_id,
            site_id=event.site_id,
            missing_fields=list(event.missing_fields),
        )


def log_planner_decision(decision: PlannerDecision) -> None:
    """Log the PlannerDecision for development visibility (not user-facing)."""
    logger.info(
        "PlannerDecision correlation_id=%s decision_type=%s workflow_key=%s reason=%s "
        "organization=%s user=%s project=%s site=%s",
        decision.correlation_id,
        decision.decision_type.value,
        decision.workflow_key.value if decision.workflow_key else "none",
        decision.reason.value,
        decision.organization_id,
        decision.user_id,
        decision.project_id or "unknown",
        decision.site_id or "unknown",
    )
    if decision.missing_fields:
        logger.info("PlannerDecision missing_fields=%s", decision.missing_fields)
