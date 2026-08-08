"""build_canonical_events' genuinely-plural path (Phase B3 of
docs/execution/UNIFIED_UNDERSTANDING_PIPELINE.md): one CanonicalEventV2 per
`understanding.intents` entry, reachable only once `len(intents) > 1` --
today that only happens via direct construction (B4 hasn't shipped, so no
real pipeline produces more than one intent yet), which is exactly what
these tests do, proving the mechanism works ahead of the prompt change that
will actually trigger it in production.

The n<=1 path (today's only reachable path in production) is covered by
test_multi_segment_canonicalization.py and is untouched by this phase --
verified byte-identical by the full suite, not just by these tests.
"""

from __future__ import annotations

from canonicalization import build_canonical_events
from mesiri_contracts.assistant.candidates import (
    AddProjectMemberCandidate,
    ProjectCreateCandidate,
    SiteCreateCandidate,
)
from mesiri_contracts.assistant.canonical_event import CanonicalEventType, IntentCompleteness
from mesiri_contracts.assistant.confidence import ConfidenceLevel
from mesiri_contracts.assistant.context_enums import ContextConfidence, ContextSource
from mesiri_contracts.assistant.enums import InputModality, SemanticType
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _context(*, project_id: str | None = None, site_id: str | None = None) -> ResolvedContextV2:
    return ResolvedContextV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        context_organization_id="org_1",
        context_user_id="usr_1",
        context_project_id=project_id,
        context_site_id=site_id,
        organization_id=ORG,
        user_id=USR,
        project_id=project_id,
        site_id=site_id,
        context_source=ContextSource.USER_DEFAULT,
        context_confidence=ContextConfidence.HIGH,
    )


def test_two_or_more_intents_produce_one_event_each():
    """The Bidilaj trace (docs/execution/UNIFIED_UNDERSTANDING_PIPELINE.md
    §1): three intents in, three events out -- the shape B4's prompt change
    exists to make real."""
    understanding = UnderstandingResult(
        source_message_id="msg_1",
        correlation_id="cor_1",
        input_modality=InputModality.TEXT,
        intents=[
            ProjectCreateCandidate(fields={"name": "Bidilaj"}),
            SiteCreateCandidate(fields={"name": "Site A"}),
            AddProjectMemberCandidate(fields={"member_name": "Usman", "role": "site_engineer"}),
        ],
        overall_confidence=ConfidenceLevel.HIGH,
    )

    events = build_canonical_events(understanding, _context())

    assert len(events) == 3
    assert events[0].event_type is CanonicalEventType.PROJECT_CREATE_REQUESTED
    assert events[0].fields["name"] == "Bidilaj"
    assert events[1].event_type is CanonicalEventType.SITE_CREATE_REQUESTED
    assert events[1].fields["name"] == "Site A"
    assert events[2].event_type is CanonicalEventType.ADD_PROJECT_MEMBER_REQUESTED
    assert events[2].fields["member_name"] == "Usman"
    # Every event traces back to the same message.
    assert {e.correlation_id for e in events} == {"cor_1"}
    assert {e.source_message_id for e in events} == {"msg_1"}
    # Each event gets its own identity, never shared/reused.
    assert len({e.event_id for e in events}) == 3


def test_plural_events_share_message_level_context():
    """organization_id/project_id/site_id/permissions are properties of the
    SENDER and the resolved context, not of any one intent -- every event
    built from one message must carry the same values, exactly as the
    single-event path already guarantees."""
    project_id = "55555555-5555-4555-8555-555555555555"
    site_id = "66666666-6666-4666-8666-666666666666"
    context = _context(project_id=project_id, site_id=site_id)
    understanding = UnderstandingResult(
        source_message_id="msg_1",
        correlation_id="cor_1",
        input_modality=InputModality.TEXT,
        intents=[
            ProjectCreateCandidate(fields={"name": "Bidilaj"}),
            SiteCreateCandidate(fields={"name": "Site A"}),
        ],
        overall_confidence=ConfidenceLevel.HIGH,
    )

    events = build_canonical_events(understanding, context)

    assert len(events) == 2
    for event in events:
        assert event.organization_id == ORG
        assert event.project_id == project_id
        assert event.site_id == site_id


def test_a_missing_required_field_on_one_intent_does_not_sink_the_others():
    """Each intent's own completeness/missing_fields is computed
    independently -- one segment needing clarification must not affect the
    others' own event_type/completeness."""
    understanding = UnderstandingResult(
        source_message_id="msg_1",
        correlation_id="cor_1",
        input_modality=InputModality.TEXT,
        intents=[
            ProjectCreateCandidate(fields={"name": "Bidilaj"}),
            # No member_name at all -- ADD_PROJECT_MEMBER_REQUESTED requires it.
            AddProjectMemberCandidate(fields={}),
        ],
        overall_confidence=ConfidenceLevel.HIGH,
    )

    events = build_canonical_events(understanding, _context())

    assert len(events) == 2
    assert events[0].completeness is IntentCompleteness.ACTIONABLE
    assert events[1].event_type is CanonicalEventType.CLARIFICATION_REQUIRED
    assert events[1].completeness is IntentCompleteness.NEEDS_CLARIFICATION
    assert "member_name" in events[1].missing_fields


def test_unknown_semantic_type_string_on_one_intent_degrades_to_unknown():
    """An intent whose semantic_type isn't a real SemanticType value (a
    provider hallucination on just one entry, in a genuinely-plural
    response) degrades that ONE event to UNKNOWN/UNRECOGNIZED, same as the
    single-intent path already does for the primary -- it must not raise
    and must not affect the other, valid intents."""
    from mesiri_contracts.assistant.candidates import Candidate

    understanding = UnderstandingResult(
        source_message_id="msg_1",
        correlation_id="cor_1",
        input_modality=InputModality.TEXT,
        intents=[
            ProjectCreateCandidate(fields={"name": "Bidilaj"}),
            Candidate(semantic_type=SemanticType.UNKNOWN, fields={"foo": "bar"}),
        ],
        overall_confidence=ConfidenceLevel.HIGH,
    )
    # Force an invalid raw string past the enum to exercise the ValueError
    # branch exactly as the single-event path's own try/except does.
    understanding.intents[1].semantic_type = "not_a_real_semantic_type"  # type: ignore[assignment]

    events = build_canonical_events(understanding, _context())

    assert len(events) == 2
    assert events[0].event_type is CanonicalEventType.PROJECT_CREATE_REQUESTED
    assert events[1].event_type is CanonicalEventType.UNRECOGNIZED
