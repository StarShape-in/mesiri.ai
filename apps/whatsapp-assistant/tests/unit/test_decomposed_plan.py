"""Unit tests for runtime/inbound_journey/decomposed_plan.py -- the wiring
that gives an UNKNOWN-classified message a second chance to become a
multi-step Plan (docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §9).

Fakes only, but exercises the REAL chain: decompose -> per-segment extract
via a real UnderstandingPipeline -> build_canonical_event -> entity linking
-> PlanStore.start_plan (all-PENDING) -> the whole-plan preview (§8). No
WorkflowRuntime involved here at all: this function never starts a workflow,
only persists a plan and describes it -- see test_plan_confirmation.py for
what happens once the user actually taps Yes.
"""

from __future__ import annotations

from typing import Any

from mesiri.infrastructure.objectstorage.fake import FakeObjectStorage
from mesiri_ai.fakes import (
    FakeDecompositionProvider,
    FakeVisionProvider,
    FakeVoiceExtractionProvider,
)
from mesiri_ai.models import DecompositionResult, ExtractionResult
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2
from planning.plan import StepStatus
from planning.plan_store import PlanStore
from runtime.inbound_journey.decomposed_plan import try_start_decomposed_plan
from understanding.pipeline import UnderstandingPipeline

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def namespaced(self, *parts: str) -> str:
        return ":".join(parts)

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        self._store[key] = value

    async def get_json(self, key: str) -> Any | None:
        return self._store.get(key)


class _SequentialExtractionProvider:
    """Returns a different canned ExtractionResult per call, in order --
    what a real provider does when given a different segment each time.
    FakeExtractionProvider only supports one fixed result for every call."""

    provider = "fake"

    def __init__(self, results: list[ExtractionResult]) -> None:
        self._results = list(results)
        self.calls = 0
        self.texts: list[str] = []

    async def extract(self, text, *, semantic_hint=None, expense_categories=None, correlation_id=None):
        self.texts.append(text)
        result = self._results[self.calls]
        self.calls += 1
        return result


def _understanding(*, normalized_text: str) -> UnderstandingResult:
    return UnderstandingResult(
        source_message_id="msg_1",
        correlation_id="cor_1",
        input_modality=InputModality.TEXT,
        normalized_text=normalized_text,
    )


def _resolved_context() -> ResolvedContextV2:
    return ResolvedContextV2(
        correlation_id="cor_1",
        source_message_id="msg_1",
        conversation_id="conv_1",
        context_organization_id=ORG,
        context_user_id=USR,
        organization_id=ORG,
        user_id=USR,
        permissions=["projects:write", "sites:write", "users:write"],
    )


async def _pipeline(extraction) -> UnderstandingPipeline:
    return UnderstandingPipeline(
        voice_extraction=FakeVoiceExtractionProvider(),
        vision=FakeVisionProvider(),
        extraction=extraction,
        object_storage=FakeObjectStorage(),
    )


async def test_returns_none_when_no_decomposition_provider_is_wired():
    """The overwhelmingly common deployment state today -- must be a cheap,
    silent no-op so the caller falls through to its existing behaviour."""
    reply = await try_start_decomposed_plan(
        message_modality=InputModality.TEXT,
        understanding=_understanding(normalized_text="asdkjhaskjdh"),
        resolved=_resolved_context(),
        pipeline=await _pipeline(_SequentialExtractionProvider([])),
        decomposition=None,
        plan_store=PlanStore(_FakeRedis()),
        expense_categories=None,
        correlation_id="cor_1",
    )
    assert reply is None


async def test_returns_none_for_a_non_decomposable_modality():
    reply = await try_start_decomposed_plan(
        message_modality=InputModality.IMAGE,
        understanding=_understanding(normalized_text="whatever"),
        resolved=_resolved_context(),
        pipeline=await _pipeline(_SequentialExtractionProvider([])),
        decomposition=FakeDecompositionProvider(
            DecompositionResult(is_multi_intent=True, segments=["a", "b"])
        ),
        plan_store=PlanStore(_FakeRedis()),
        expense_categories=None,
        correlation_id="cor_1",
    )
    assert reply is None


async def test_returns_none_when_decomposition_says_not_multi_intent():
    """Genuine gibberish/one real intent must fall through to today's
    ordinary unrecognized-message reply, not become a size-1 "plan"."""
    reply = await try_start_decomposed_plan(
        message_modality=InputModality.TEXT,
        understanding=_understanding(normalized_text="asdkjhaskjdh"),
        resolved=_resolved_context(),
        pipeline=await _pipeline(_SequentialExtractionProvider([])),
        decomposition=FakeDecompositionProvider(DecompositionResult(is_multi_intent=False)),
        plan_store=PlanStore(_FakeRedis()),
        expense_categories=None,
        correlation_id="cor_1",
    )
    assert reply is None


async def test_returns_none_when_decomposition_provider_raises():
    class _Boom:
        provider = "boom"

        async def decompose(self, text, *, correlation_id=None):
            raise RuntimeError("provider outage")

    reply = await try_start_decomposed_plan(
        message_modality=InputModality.TEXT,
        understanding=_understanding(normalized_text="whatever"),
        resolved=_resolved_context(),
        pipeline=await _pipeline(_SequentialExtractionProvider([])),
        decomposition=_Boom(),
        plan_store=PlanStore(_FakeRedis()),
        expense_categories=None,
        correlation_id="cor_1",
    )
    assert reply is None


async def test_the_starship_message_produces_the_whole_plan_preview():
    """The scenario that motivated all of this: "create a project called
    Starship and then create a site called Site A, then create a new user
    Hysam, 9198765xxxxx" -- decompose -> per-segment extract -> canonicalize
    -> link -> persist all-PENDING -> the §8 preview, not a running step.

    The user segment states BOTH full_name and whatsapp_number -- see
    test_a_deferred_required_field_drops_the_segment_from_the_plan below for
    what happens to §9's original example, where the number was promised in
    a follow-up message instead of stated in the same breath.
    """
    decomposition = FakeDecompositionProvider(
        DecompositionResult(
            is_multi_intent=True,
            segments=[
                "create a project called Starship",
                "create a site called Site A",
                "create a new user named Hysam, 9198765xxxxx",
            ],
        )
    )
    extraction = _SequentialExtractionProvider(
        [
            ExtractionResult(
                semantic_type="project_create", fields={"name": "Starship"}, provider="fake"
            ),
            ExtractionResult(
                semantic_type="site_create", fields={"name": "Site A"}, provider="fake"
            ),
            ExtractionResult(
                semantic_type="create_user",
                fields={"full_name": "Hysam", "whatsapp_number": "9198765xxxxx"},
                provider="fake",
            ),
        ]
    )
    plan_store = PlanStore(_FakeRedis())

    reply = await try_start_decomposed_plan(
        message_modality=InputModality.TEXT,
        understanding=_understanding(
            normalized_text=(
                "create a project called Starship and then create a site called Site A, "
                "then create a new user named Hysam, 9198765xxxxx"
            )
        ),
        resolved=_resolved_context(),
        pipeline=await _pipeline(extraction),
        decomposition=decomposition,
        plan_store=plan_store,
        expense_categories=None,
        correlation_id="cor_starship",
    )

    assert reply is not None
    assert reply.text.startswith("I'll do 3 things:")
    assert "Create project Starship" in reply.text
    assert "Create site Site A under Starship" in reply.text
    assert "Add Hysam (9198765xxxxx) as a new user" in reply.text
    # Yes/No, not a per-step confirmation -- nothing has started.
    assert reply.buttons is not None
    assert {b.title for b in reply.buttons} == {"Yes", "No"}
    assert decomposition.calls == 1
    assert extraction.calls == 3

    plan = await plan_store.get_plan(user_id=USR)
    assert plan is not None
    assert len(plan.steps) == 3
    assert all(s.status is StepStatus.PENDING for s in plan.steps)


async def test_a_deferred_required_field_drops_the_segment_from_the_plan():
    """A KNOWN V1 GAP, not a bug in this test: §9's original real message
    said "create a new user named Hysam, I'll send his number now" -- the
    number arrives in a LATER, separate message. canonicalization's own
    REQUIRED_FIELDS gate (mapping.py) requires whatsapp_number for
    CREATE_USER_REQUESTED, so this segment canonicalizes to
    CLARIFICATION_REQUIRED, which routing.py's WORKFLOW_KEY_BY_EVENT has no
    entry for by design (its docstring: CLARIFICATION_REQUIRED never starts
    a workflow) -- so build_plan_from_segments correctly, silently drops it,
    the same as any other unroutable segment.

    This differs from the single-message path, where the SAME missing field
    gets render_clarify_reply's targeted "Almost there -- I still need
    WhatsApp number" (channel/replies.py) -- and from the entity-resolution
    layer's offer-driven create (resume.py's start_member_create_plan),
    which hand-builds its CanonicalEventV2 and so never goes through this
    gate at all. Neither escape hatch exists for a decomposed segment yet.
    Silent (not a failure or a misleading reply) is the deliberate interim
    choice: the project still gets its own step in the plan, which is still
    real progress on the message, and is safer than guessing at a phone
    number. Surfacing this to the user ("I couldn't include Hysam yet --
    also send me his number") is real follow-up work, now that the preview
    exists to say it in.
    """
    decomposition = FakeDecompositionProvider(
        DecompositionResult(
            is_multi_intent=True,
            segments=[
                "create a project called Starship",
                "create a new user named Hysam",  # no phone number stated
            ],
        )
    )
    extraction = _SequentialExtractionProvider(
        [
            ExtractionResult(
                semantic_type="project_create", fields={"name": "Starship"}, provider="fake"
            ),
            ExtractionResult(
                semantic_type="create_user", fields={"full_name": "Hysam"}, provider="fake"
            ),
        ]
    )
    plan_store = PlanStore(_FakeRedis())

    reply = await try_start_decomposed_plan(
        message_modality=InputModality.TEXT,
        understanding=_understanding(
            normalized_text="create a project called Starship, then a new user named Hysam"
        ),
        resolved=_resolved_context(),
        pipeline=await _pipeline(extraction),
        decomposition=decomposition,
        plan_store=plan_store,
        expense_categories=None,
        correlation_id="cor_1",
    )

    assert reply is not None
    assert reply.text.startswith("I'll do this:")  # only the project step made it into the plan
    plan = await plan_store.get_plan(user_id=USR)
    assert [s.step_id for s in plan.steps] == ["s1"]


async def test_a_segment_that_fails_to_understand_does_not_sink_the_rest():
    decomposition = FakeDecompositionProvider(
        DecompositionResult(is_multi_intent=True, segments=["good segment", "bad segment"])
    )

    class _PartlyFailingExtraction:
        provider = "fake"

        def __init__(self) -> None:
            self.calls = 0

        async def extract(self, text, **kwargs):
            self.calls += 1
            if text == "bad segment":
                raise RuntimeError("extraction blew up")
            return ExtractionResult(
                semantic_type="project_create", fields={"name": "Starship"}, provider="fake"
            )

    plan_store = PlanStore(_FakeRedis())

    reply = await try_start_decomposed_plan(
        message_modality=InputModality.TEXT,
        understanding=_understanding(normalized_text="good segment. bad segment."),
        resolved=_resolved_context(),
        pipeline=await _pipeline(_PartlyFailingExtraction()),
        decomposition=decomposition,
        plan_store=plan_store,
        expense_categories=None,
        correlation_id="cor_1",
    )

    assert reply is not None
    plan = await plan_store.get_plan(user_id=USR)
    assert len(plan.steps) == 1  # the failing segment never became a step


async def test_no_plannable_segments_falls_through_to_none():
    """Every segment came back unroutable (e.g. all UNKNOWN again) -- no
    plan is worth starting, so the caller's ordinary fallback applies."""
    decomposition = FakeDecompositionProvider(
        DecompositionResult(is_multi_intent=True, segments=["gibberish one", "gibberish two"])
    )
    extraction = _SequentialExtractionProvider(
        [
            ExtractionResult(semantic_type="unknown", provider="fake"),
            ExtractionResult(semantic_type="unknown", provider="fake"),
        ]
    )
    reply = await try_start_decomposed_plan(
        message_modality=InputModality.TEXT,
        understanding=_understanding(normalized_text="gibberish one. gibberish two."),
        resolved=_resolved_context(),
        pipeline=await _pipeline(extraction),
        decomposition=decomposition,
        plan_store=PlanStore(_FakeRedis()),
        expense_categories=None,
        correlation_id="cor_1",
    )
    assert reply is None
