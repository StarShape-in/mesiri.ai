"""build_canonical_events (#1 Multi-Activity, #13 Cross-Module Trigger) --
the deterministic work_item-linked second segment, and everything it must
NOT trigger for.
"""

from __future__ import annotations

from canonicalization import build_canonical_event, build_canonical_events
from mesiri_contracts.assistant.candidates import ExpenseCandidate, MaterialUpdateCandidate
from mesiri_contracts.assistant.canonical_event import CanonicalEventType, IntentCompleteness
from mesiri_contracts.assistant.confidence import ConfidenceLevel
from mesiri_contracts.assistant.context_enums import ContextConfidence, ContextSource
from mesiri_contracts.assistant.enums import InputModality, SemanticType
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"
SITE = "44444444-4444-4444-8444-444444444444"


def _understanding(*, semantic_type: SemanticType, candidates) -> UnderstandingResult:
    return UnderstandingResult(
        source_message_id="msg_1",
        correlation_id="cor_1",
        input_modality=InputModality.TEXT,
        semantic_type=semantic_type,
        candidates=candidates,
        overall_confidence=ConfidenceLevel.HIGH,
    )


def _context() -> ResolvedContextV2:
    return ResolvedContextV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        context_organization_id="org_1",
        context_user_id="usr_1",
        context_project_id="prj_1",
        context_site_id="site_1",
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        site_id=SITE,
        context_source=ContextSource.USER_DEFAULT,
        context_confidence=ContextConfidence.HIGH,
    )


def test_events0_always_matches_the_singular_builder_exactly():
    """events[0] must be pixel-identical (bar event_id, which is freshly
    minted each call) to what build_canonical_event alone produces -- every
    existing single-segment caller depends on this being true."""
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE,
        candidates=[
            MaterialUpdateCandidate(
                fields={"material_name": "cement", "quantity": 40, "unit": "bags", "direction": "used"}
            )
        ],
    )
    single = build_canonical_event(understanding, _context())
    events = build_canonical_events(understanding, _context())

    assert len(events) == 1
    assert events[0].event_type == single.event_type
    assert events[0].completeness == single.completeness
    assert events[0].fields == single.fields


def test_material_usage_with_work_item_produces_a_linked_second_segment():
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE,
        candidates=[
            MaterialUpdateCandidate(
                fields={
                    "material_name": "cement",
                    "quantity": 40,
                    "unit": "bags",
                    "direction": "used",
                    "work_item": "plastering Block A",
                }
            )
        ],
    )
    events = build_canonical_events(understanding, _context())

    assert len(events) == 2
    assert events[0].event_type is CanonicalEventType.MATERIAL_USAGE_REQUESTED
    assert events[1].event_type is CanonicalEventType.ACTIVITY_CONTINUATION_REQUESTED
    assert events[1].completeness is IntentCompleteness.ACTIONABLE
    assert events[1].fields["narrative"] == "plastering Block A"
    # Causally linked back to the segment that produced it.
    assert events[1].causation_id == events[0].event_id
    # Same correlation_id -- never regenerated, both segments trace back to
    # the same inbound message.
    assert events[1].correlation_id == events[0].correlation_id
    # Same scope as the primary segment.
    assert events[1].organization_id == events[0].organization_id
    assert events[1].project_id == events[0].project_id
    assert events[1].site_id == events[0].site_id


def test_material_receipt_with_work_item_also_links():
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE,
        candidates=[
            MaterialUpdateCandidate(
                fields={
                    "material_name": "cement",
                    "quantity": 100,
                    "unit": "bags",
                    "direction": "received",
                    "work_item": "for the plastering crew",
                }
            )
        ],
    )
    events = build_canonical_events(understanding, _context())
    assert len(events) == 2
    assert events[0].event_type is CanonicalEventType.MATERIAL_RECEIPT_REQUESTED
    assert events[1].event_type is CanonicalEventType.ACTIVITY_CONTINUATION_REQUESTED


def test_material_usage_without_work_item_stays_a_single_segment():
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE,
        candidates=[
            MaterialUpdateCandidate(
                fields={"material_name": "cement", "quantity": 40, "unit": "bags", "direction": "used"}
            )
        ],
    )
    events = build_canonical_events(understanding, _context())
    assert len(events) == 1


def test_incomplete_material_report_never_synthesizes_a_second_segment():
    """A material report missing a required field resolves to
    CLARIFICATION_REQUIRED, not MATERIAL_USAGE_REQUESTED -- the work_item
    linking check must only fire on a genuinely ACTIONABLE primary."""
    understanding = _understanding(
        semantic_type=SemanticType.MATERIAL_UPDATE,
        candidates=[
            MaterialUpdateCandidate(
                fields={"direction": "used", "work_item": "plastering Block A"}
            )
        ],
    )
    events = build_canonical_events(understanding, _context())
    assert len(events) == 1
    assert events[0].completeness is not IntentCompleteness.ACTIONABLE


def test_non_material_event_types_never_synthesize_a_linked_segment():
    understanding = _understanding(
        semantic_type=SemanticType.EXPENSE,
        candidates=[ExpenseCandidate(fields={"amount": 500, "work_item": "plastering Block A"})],
    )
    events = build_canonical_events(understanding, _context())
    assert len(events) == 1
