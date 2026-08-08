"""Planner (M5) — reads CanonicalEvent v2, returns PlannerDecision v2."""

from __future__ import annotations

import logging

from mesiri_contracts.assistant.canonical_event import (
    CanonicalEventType,
    IntentCompleteness,
)
from mesiri_contracts.assistant.planner_decision import PlannerDecisionType, PlannerPriority
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2

from .routing import WORKFLOW_KEY_BY_EVENT

logger = logging.getLogger(__name__)


class Planner:
    """Routes a CanonicalEvent v2 to a PlannerDecision v2."""

    def decide(self, event: CanonicalEventV2) -> PlannerDecisionV2:
        if event.completeness is IntentCompleteness.ACTIONABLE:
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

        return PlannerDecisionV2(
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


def log_planner_decision(decision: PlannerDecisionV2) -> None:
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
