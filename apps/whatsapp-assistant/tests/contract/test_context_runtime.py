"""Runtime integration: NormalizedMessage → Understanding → Context → Planner → Workflow → reply.

Context resolution uses M4 seed fakes so the tests run without a live
database. WorkflowRuntime here always uses a FakeWorkflowRegistry/
FakeWorkflowInstanceRepository — no LangGraph import needed, matching the
core-suite-runs-without-langgraph invariant. The key invariants:
  - process_inbound_message wires Understanding → Context → Canonicalization → Planner → Workflow → reply
  - a reply is always sent, whatever the context resolution outcome
  - the reply is never format_reply()'s developer diagnostic
  - build_container wires an M4 ContextResolver (not ContractContextResolver)
  - context_debug flag triggers log output from log_resolved_context / log_canonical_event /
    log_planner_decision / log_workflow_run
  - when a workflow actually starts, the reply is the workflow's confirmation prompt
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx

from channel.replies import render_understanding_failed_reply, render_unsupported_reply
from context import seed
from context.identity_bridge import deterministic_canonical_uuid as canon
from context.resolver import ContextResolver
from interactions import InteractionHandler
from mesiri.infrastructure.objectstorage.fake import FakeObjectStorage
from mesiri_ai import fixtures
from mesiri_ai.fakes import (
    FakeExtractionProvider,
    FakeSpeechProvider,
    FakeTranslationProvider,
    FakeVisionProvider,
)
from mesiri_ai.models import ExtractionResult
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import (
    MediaReference,
    NormalizedMessage,
    SenderInfo,
)
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.assistant.v2.planner_decision import PlannerDecisionV2
from mesiri_contracts.assistant.v2.resolved_context import ResolvedContextV2
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2
from mesiri_contracts.context.enums import WorkflowPhase
from planner import Planner
from runtime.dependencies import Settings, build_container
from runtime.inbound_journey import process_inbound_message
from understanding.pipeline import UnderstandingPipeline
from understanding.runtime import format_reply
from workflows import WorkflowRuntime
from workflows.fakes import FakeCompiledGraph, FakeWorkflowInstanceRepository, FakeWorkflowRegistry
from workflows.runtime import WorkflowRunStatus


def _message(wa_id: str = seed.WA_ENGINEER, **kwargs) -> NormalizedMessage:
    base = dict(
        message_id="wamid.context.1",
        correlation_id="cor_context_1",
        sender=SenderInfo(wa_id=wa_id, profile_name="Engineer"),
        timestamp=datetime(2026, 7, 6, 10, 0, tzinfo=UTC),
        modality=InputModality.TEXT,
        text="paid 1500 to ABC Hardware",
    )
    base.update(kwargs)
    return NormalizedMessage(**base)


def _pipeline() -> UnderstandingPipeline:
    return UnderstandingPipeline(
        speech=FakeSpeechProvider(fixtures.MALAYALAM_JCB_SPEECH),
        vision=FakeVisionProvider(fixtures.VALID_RECEIPT_VISION),
        extraction=FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION),
        translation=FakeTranslationProvider(),
        object_storage=FakeObjectStorage(),
    )


def _resolver() -> ContextResolver:
    """M4 ContextResolver wired with seed fakes (no live DB required)."""
    return ContextResolver(seed.build_dependencies())


def _workflow_runtime(
    graphs: dict[WorkflowKey, FakeCompiledGraph] | None = None,
) -> WorkflowRuntime:
    """A WorkflowRuntime backed entirely by fakes — no LangGraph, no DB."""
    return WorkflowRuntime(
        registry=FakeWorkflowRegistry(graphs),
        repo=FakeWorkflowInstanceRepository(),
    )


async def _noop_send_text(wa_id: str, body: str) -> None:
    return None


async def test_inbound_journey_produces_resolved_context():
    message = _message()
    pipeline = _pipeline()
    context_resolver = _resolver()
    sent_replies: list[str] = []

    async def capture_send(wa_id: str, body: str) -> None:
        sent_replies.append(body)

    result = await process_inbound_message(
        message,
        actor_user_id=canon(seed.USER_ENGINEER),
        pipeline=pipeline,
        context_resolver=context_resolver,
        planner=Planner(),
        workflow_runtime=_workflow_runtime(),
        interaction_handler=InteractionHandler(_workflow_runtime()),
        send_text=capture_send,
    )

    assert isinstance(result.understanding, UnderstandingResult)
    # seed.WA_ENGINEER is registered in seed fakes → resolution succeeds
    assert isinstance(result.resolved_context, ResolvedContextV2)
    assert result.resolved_context.correlation_id == message.correlation_id
    assert result.resolved_context.source_message_id == message.message_id
    assert result.resolved_context.context_user_id == seed.USER_ENGINEER
    assert result.resolved_context.context_organization_id == seed.ORG_A
    assert result.resolved_context.user_id == canon(seed.USER_ENGINEER)
    assert result.resolved_context.organization_id == canon(seed.ORG_A)
    # No graph registered for expense.submit in this fake registry -> NO_GRAPH,
    # which tells the user we understood but can't record it yet. It must never
    # be the "I couldn't make out that message" reply: the message was fine.
    assert sent_replies == [render_unsupported_reply()]

    # Context resolved successfully → canonicalization and planning run too.
    assert isinstance(result.canonical_event, CanonicalEventV2)
    assert result.canonical_event.correlation_id == message.correlation_id
    assert result.canonical_event.organization_id == canon(seed.ORG_A)
    assert result.canonical_event.user_id == canon(seed.USER_ENGINEER)

    assert isinstance(result.planner_decision, PlannerDecisionV2)
    assert result.planner_decision.correlation_id == message.correlation_id
    assert result.planner_decision.organization_id == canon(seed.ORG_A)
    assert result.planner_decision.user_id == canon(seed.USER_ENGINEER)


async def test_inbound_journey_never_sends_the_developer_diagnostic():
    """format_reply() renders "Type: ... / Confidence: ..." — a developer
    diagnostic. It must never reach a user, on any path.

    Supersedes the old contract "reply content must not depend on whether
    context resolved": the reply now derives from the PlannerDecision, so it
    depends on context by design.
    """
    message = _message()
    pipeline = _pipeline()

    diagnostic = format_reply(await pipeline.understand(message))
    captured: list[str] = []

    async def capture_send(wa_id: str, body: str) -> None:
        captured.append(body)

    await process_inbound_message(
        message,
        actor_user_id=canon(seed.USER_ENGINEER),
        pipeline=pipeline,
        context_resolver=_resolver(),
        planner=Planner(),
        workflow_runtime=_workflow_runtime(),
        interaction_handler=InteractionHandler(_workflow_runtime()),
        send_text=capture_send,
    )

    assert captured and diagnostic not in captured
    assert not any("Confidence:" in body for body in captured)


async def test_inbound_journey_unknown_user_still_sends_reply():
    """An unregistered wa_id causes context to fail, but a reply is still sent.

    The identity gate in _on_normalized blocks unregistered users before
    process_inbound_message is called. This test verifies that if context
    resolution fails for any reason, the user still hears something back —
    silence is indistinguishable from Mesiri being down.
    """
    message = _message(wa_id="wa_unregistered_999")
    pipeline = _pipeline()
    context_resolver = _resolver()
    sent_replies: list[str] = []

    async def capture_send(wa_id: str, body: str) -> None:
        sent_replies.append(body)

    result = await process_inbound_message(
        message,
        actor_user_id="wa_unregistered_999",
        pipeline=pipeline,
        context_resolver=context_resolver,
        planner=Planner(),
        workflow_runtime=_workflow_runtime(),
        interaction_handler=InteractionHandler(_workflow_runtime()),
        send_text=capture_send,
    )

    assert isinstance(result.understanding, UnderstandingResult)
    assert result.resolved_context is None  # context failed gracefully
    assert result.canonical_event is None  # canonicalization requires resolved context
    assert result.planner_decision is None  # no canonical event to plan from
    assert result.workflow_run is None  # no planner decision to act on
    assert sent_replies == [render_understanding_failed_reply()]


async def test_inbound_journey_starts_workflow_and_replies_with_confirmation_prompt():
    """When Planner emits START_WORKFLOW and a graph is registered, the reply is
    the workflow's confirmation prompt — never the understanding summary."""
    message = _message()
    pipeline = UnderstandingPipeline(
        speech=FakeSpeechProvider(fixtures.MALAYALAM_JCB_SPEECH),
        vision=FakeVisionProvider(fixtures.VALID_RECEIPT_VISION),
        extraction=FakeExtractionProvider(
            ExtractionResult(
                semantic_type="material_update",
                fields={
                    "material_name": "cement",
                    "quantity": 20,
                    "unit": "bags",
                    "direction": "received",
                },
                field_confidences={
                    "material_name": 0.98,
                    "quantity": 0.97,
                    "unit": 0.95,
                    "direction": 0.9,
                },
                model="fake-gemini",
                latency_ms=180.0,
            )
        ),
        translation=FakeTranslationProvider(),
        object_storage=FakeObjectStorage(),
    )
    context_resolver = _resolver()

    draft = DraftActionV2(
        draft_id="draft_test",
        correlation_id="cor_context_1",
        workflow_instance_id="placeholder",
        action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
        organization_id=canon(seed.ORG_A),
        user_id=canon(seed.USER_ENGINEER),
        fields={"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    fake_graph = FakeCompiledGraph(
        {"draft_action": draft, "pending_prompt": "Confirm: 20 bags cement received?"}
    )
    workflow_runtime = _workflow_runtime({WorkflowKey.MATERIAL_RECEIPT: fake_graph})

    sent_texts: list[tuple[str, str]] = []
    sent_buttons: list[tuple[str, str, tuple]] = []

    async def capture_send_text(wa_id: str, body: str) -> None:
        sent_texts.append((wa_id, body))

    async def capture_send_button(wa_id: str, *, body: str, buttons: tuple) -> None:
        sent_buttons.append((wa_id, body, buttons))

    result = await process_inbound_message(
        message,
        actor_user_id=canon(seed.USER_ENGINEER),
        pipeline=pipeline,
        context_resolver=context_resolver,
        planner=Planner(),
        workflow_runtime=workflow_runtime,
        interaction_handler=InteractionHandler(workflow_runtime),
        send_text=capture_send_text,
        send_button=capture_send_button,
    )

    assert result.planner_decision is not None
    assert result.planner_decision.workflow_key is WorkflowKey.MATERIAL_RECEIPT
    assert result.workflow_run is not None
    assert result.workflow_run.status is WorkflowRunStatus.STARTED
    assert result.workflow_run.pending_prompt == "Confirm: 20 bags cement received?"
    # A confirmation prompt is sent as Yes/No buttons, not plain text -- see
    # runtime/inbound_journey.py's _render_reply.
    assert sent_texts == []
    assert len(sent_buttons) == 1
    wa_id, body, buttons = sent_buttons[0]
    assert wa_id == message.sender.wa_id
    assert body == "Confirm: 20 bags cement received?"
    assert [b.id for b in buttons] == ["confirm_yes", "confirm_no"]


def _material_pipeline() -> UnderstandingPipeline:
    return UnderstandingPipeline(
        speech=FakeSpeechProvider(fixtures.MALAYALAM_JCB_SPEECH),
        vision=FakeVisionProvider(fixtures.VALID_RECEIPT_VISION),
        extraction=FakeExtractionProvider(
            ExtractionResult(
                semantic_type="material_update",
                fields={
                    "material_name": "cement",
                    "quantity": 20,
                    "unit": "bags",
                    "direction": "received",
                },
                field_confidences={
                    "material_name": 0.98,
                    "quantity": 0.97,
                    "unit": 0.95,
                    "direction": 0.9,
                },
                model="fake-gemini",
                latency_ms=180.0,
            )
        ),
        translation=FakeTranslationProvider(),
        object_storage=FakeObjectStorage(),
    )


async def test_inbound_journey_blocks_new_workflow_while_confirmation_pending():
    """Single-active invariant: an actionable intent arriving while a confirmation
    is pending is blocked and re-shows the pending prompt (not a new draft)."""
    message = _message()
    context_resolver = _resolver()

    # Pre-seed an awaiting-confirmation workflow for the resolved user.
    pending = WorkflowStateV2(
        workflow_instance_id="11111111-1111-4111-8111-1111111111aa",
        workflow_key=WorkflowKey.MATERIAL_RECEIPT,
        correlation_id="cor_prev",
        organization_id=canon(seed.ORG_A),
        user_id=canon(seed.USER_ENGINEER),
        phase=WorkflowPhase.AWAITING_CONFIRMATION,
        draft_action=DraftActionV2(
            draft_id="draft_prev",
            correlation_id="cor_prev",
            workflow_instance_id="11111111-1111-4111-8111-1111111111aa",
            action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
            organization_id=canon(seed.ORG_A),
            user_id=canon(seed.USER_ENGINEER),
            fields={"material_name": "steel", "quantity": 10, "unit": "rods"},
        ),
        pending_prompt="Confirm: 10 rods steel received?",
    )
    repo = FakeWorkflowInstanceRepository()
    repo.seed(pending, version=0)
    graph = FakeCompiledGraph({"draft_action": None, "pending_prompt": "x"})
    workflow_runtime = WorkflowRuntime(
        registry=FakeWorkflowRegistry({WorkflowKey.MATERIAL_RECEIPT: graph}), repo=repo
    )

    sent_texts: list[str] = []
    sent_buttons: list[tuple[str, str, tuple]] = []

    async def capture_send_text(wa_id: str, body: str) -> None:
        sent_texts.append(body)

    async def capture_send_button(wa_id: str, *, body: str, buttons: tuple) -> None:
        sent_buttons.append((wa_id, body, buttons))

    result = await process_inbound_message(
        message,
        actor_user_id=canon(seed.USER_ENGINEER),
        pipeline=_material_pipeline(),
        context_resolver=context_resolver,
        planner=Planner(),
        workflow_runtime=workflow_runtime,
        interaction_handler=InteractionHandler(workflow_runtime),
        send_text=capture_send_text,
        send_button=capture_send_button,
    )

    assert result.workflow_run is not None
    assert result.workflow_run.status is WorkflowRunStatus.BLOCKED_PENDING_CONFIRMATION
    # The "please finish the pending confirmation first" re-show is still a
    # confirmation prompt -- Yes/No buttons, not plain text (see
    # runtime/inbound_journey.py's _render_reply).
    assert sent_texts == []
    assert len(sent_buttons) == 1
    _, body, buttons = sent_buttons[0]
    assert "Confirm: 10 rods steel received?" in body
    assert [b.id for b in buttons] == ["confirm_yes", "confirm_no"]
    # the pre-existing pending workflow is untouched — no second instance created
    assert len(repo.saved) == 1


async def test_build_container_wires_context_resolver(tmp_path):
    settings = Settings(
        verify_token="test-verify-token",
        app_secret="test-app-secret",
        access_token="test-access-token",
        media_download_dir=str(tmp_path / "media"),
    )
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        container = build_container(settings, http_client)

    assert container.context_resolver is not None
    assert isinstance(container.context_resolver, ContextResolver)
    assert container.planner is not None
    assert isinstance(container.planner, Planner)
    assert container.workflow_runtime is not None
    assert isinstance(container.workflow_runtime, WorkflowRuntime)
    assert container.interaction_handler is not None
    assert isinstance(container.interaction_handler, InteractionHandler)
    # M8: the interaction handler must be wired with an execution dispatcher,
    # not left running M7-only (which would silently skip domain execution).
    assert container.interaction_handler._dispatcher is not None
    assert container.material_db is not None
    # object_storage was built locally in build_container (used for
    # build_pipeline/WhatsAppReceiver) but never attached to the returned
    # AppContainer -- backend/src/mesiri/infrastructure/objectstorage/
    # dependency.py's get_object_storage() falls back to
    # `request.app.state.container.object_storage` for the real production
    # app (runtime/lifecycle.py), so a missing field here meant every
    # expense-attachment/receipt fetch 500'd with AttributeError, in
    # production, for every user, always.
    assert container.object_storage is not None


async def test_context_debug_logs_resolved_context(caplog):
    import logging

    caplog.set_level(logging.INFO, logger="context.runtime")
    message = _message()

    async def noop_reply(msg: NormalizedMessage, understanding: UnderstandingResult) -> None:
        return None

    await process_inbound_message(
        message,
        actor_user_id=canon(seed.USER_ENGINEER),
        pipeline=_pipeline(),
        context_resolver=_resolver(),
        planner=Planner(),
        workflow_runtime=_workflow_runtime(),
        interaction_handler=InteractionHandler(_workflow_runtime()),
        send_text=_noop_send_text,
        context_debug=True,
    )

    assert any(
        "ResolvedContext correlation_id=cor_context_1" in record.message
        for record in caplog.records
    )


async def test_context_debug_logs_canonical_event(caplog):
    import logging

    caplog.set_level(logging.INFO, logger="canonicalization.builder")
    message = _message()

    async def noop_reply(msg: NormalizedMessage, understanding: UnderstandingResult) -> None:
        return None

    await process_inbound_message(
        message,
        actor_user_id=canon(seed.USER_ENGINEER),
        pipeline=_pipeline(),
        context_resolver=_resolver(),
        planner=Planner(),
        workflow_runtime=_workflow_runtime(),
        interaction_handler=InteractionHandler(_workflow_runtime()),
        send_text=_noop_send_text,
        context_debug=True,
    )

    assert any(
        "CanonicalEvent correlation_id=cor_context_1" in record.message for record in caplog.records
    )


async def test_context_debug_logs_planner_decision(caplog):
    import logging

    caplog.set_level(logging.INFO, logger="planner.planner")
    message = _message()

    async def noop_reply(msg: NormalizedMessage, understanding: UnderstandingResult) -> None:
        return None

    await process_inbound_message(
        message,
        actor_user_id=canon(seed.USER_ENGINEER),
        pipeline=_pipeline(),
        context_resolver=_resolver(),
        planner=Planner(),
        workflow_runtime=_workflow_runtime(),
        interaction_handler=InteractionHandler(_workflow_runtime()),
        send_text=_noop_send_text,
        context_debug=True,
    )

    assert any(
        "PlannerDecision correlation_id=cor_context_1" in record.message
        for record in caplog.records
    )


async def test_context_debug_logs_workflow_run(caplog):
    import logging

    caplog.set_level(logging.INFO, logger="workflows.runtime")
    message = _message()

    async def noop_reply(msg: NormalizedMessage, understanding: UnderstandingResult) -> None:
        return None

    await process_inbound_message(
        message,
        actor_user_id=canon(seed.USER_ENGINEER),
        pipeline=_pipeline(),
        context_resolver=_resolver(),
        planner=Planner(),
        workflow_runtime=_workflow_runtime(),
        interaction_handler=InteractionHandler(_workflow_runtime()),
        send_text=_noop_send_text,
        context_debug=True,
    )

    assert any(
        "WorkflowRun correlation_id=cor_context_1" in record.message for record in caplog.records
    )


async def test_reply_is_sent_once_to_the_sender():
    """Exactly one reply, addressed to the wa_id that sent the message."""
    message = _message()
    send_text = AsyncMock()

    await process_inbound_message(
        message,
        actor_user_id=canon(seed.USER_ENGINEER),
        pipeline=_pipeline(),
        context_resolver=_resolver(),
        planner=Planner(),
        workflow_runtime=_workflow_runtime(),
        interaction_handler=InteractionHandler(_workflow_runtime()),
        send_text=send_text,
    )

    # expense.submit has no graph in the fake registry -> NO_GRAPH.
    send_text.assert_awaited_once_with(message.sender.wa_id, render_unsupported_reply())


async def test_voice_reply_gets_the_same_reply_a_text_message_would():
    """Voice used to get a TEMPORARY override -- the raw transcript/translation
    echoed back, never the real reply -- to make transcription itself directly
    visible for testing. That override is gone now that voice is confirmed
    solid: a voice message flows through _render_reply exactly like text does.
    MALAYALAM_JCB_SPEECH resolves to EQUIPMENT_USAGE, which has no fake graph
    registered here, so this is NO_GRAPH -- same outcome the TEXT/NO_GRAPH
    test above asserts, just arriving via voice instead of text.
    """
    message = _message(
        modality=InputModality.VOICE,
        text=None,
        media=MediaReference(object_key="voice/1.ogg", mime_type="audio/ogg"),
    )
    storage = FakeObjectStorage()
    await storage.put_object("voice/1.ogg", b"<audio>")
    pipeline = UnderstandingPipeline(
        speech=FakeSpeechProvider(fixtures.MALAYALAM_JCB_SPEECH),
        vision=FakeVisionProvider(fixtures.VALID_RECEIPT_VISION),
        extraction=FakeExtractionProvider(fixtures.JCB_EQUIPMENT_EXTRACTION),
        translation=FakeTranslationProvider(),
        object_storage=storage,
    )
    sent_texts: list[tuple[str, str]] = []

    async def capture_send_text(wa_id: str, body: str) -> None:
        sent_texts.append((wa_id, body))

    result = await process_inbound_message(
        message,
        actor_user_id=canon(seed.USER_ENGINEER),
        pipeline=pipeline,
        context_resolver=_resolver(),
        planner=Planner(),
        workflow_runtime=_workflow_runtime(),
        interaction_handler=InteractionHandler(_workflow_runtime()),
        send_text=capture_send_text,
    )

    assert result.understanding.translated_text == "The JCB ran for 4 hours"
    assert sent_texts == [(message.sender.wa_id, render_unsupported_reply())]


async def test_inventory_query_answer_sets_a_material_hint_for_the_next_message():
    """Answering "how much cement is left?" should quietly bias the very next
    message toward material_update, so a follow-up like "40 bags used" doesn't
    fall through to the generic category menu."""
    message = _message(text="how much cement is left?")
    pipeline = UnderstandingPipeline(
        speech=FakeSpeechProvider(fixtures.MALAYALAM_JCB_SPEECH),
        vision=FakeVisionProvider(fixtures.VALID_RECEIPT_VISION),
        extraction=FakeExtractionProvider(
            ExtractionResult(
                semantic_type="inventory_query",
                fields={"material_name": "cement"},
                model="fake-gemini",
                latency_ms=90.0,
            )
        ),
        translation=FakeTranslationProvider(),
        object_storage=FakeObjectStorage(),
    )
    graph = FakeCompiledGraph({"draft_action": None, "pending_prompt": "cement: 30 bags"})
    workflow_runtime = _workflow_runtime({WorkflowKey.MATERIAL_INVENTORY_QUERY: graph})

    hints_set: list[tuple[str, str]] = []

    class _FakeHintStore:
        async def set_hint(self, *, user_id: str, semantic_hint: str) -> None:
            hints_set.append((user_id, semantic_hint))

    async def capture_send_text(wa_id: str, body: str) -> None:
        pass

    result = await process_inbound_message(
        message,
        actor_user_id=canon(seed.USER_ENGINEER),
        pipeline=pipeline,
        context_resolver=_resolver(),
        planner=Planner(),
        workflow_runtime=workflow_runtime,
        interaction_handler=InteractionHandler(workflow_runtime),
        send_text=capture_send_text,
        category_hint_store=_FakeHintStore(),
    )

    assert result.workflow_run is not None
    assert result.workflow_run.status is WorkflowRunStatus.COMPLETED
    assert hints_set == [(canon(seed.USER_ENGINEER), "material_update")]
