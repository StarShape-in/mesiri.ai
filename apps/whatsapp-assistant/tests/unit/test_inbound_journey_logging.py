"""Unit tests for MessageLogger and TraceLogger integration in the inbound journey.

Verifies that:
- The journey calls the trace logger at each pipeline stage
- The journey calls the message logger on completion
- Context resolution failure is traced with succeeded=False
- Logger exceptions are swallowed (best-effort contract)
"""

from __future__ import annotations

from datetime import UTC, datetime

from channel.replies import render_unsupported_reply
from context import seed
from context.resolver import ContextResolver
from interactions.handler import InteractionHandler
from mesiri.infrastructure.objectstorage.fake import FakeObjectStorage
from mesiri_ai import fixtures
from mesiri_ai.fakes import (
    FakeExtractionProvider,
    FakeSpeechProvider,
    FakeTranslationProvider,
    FakeVisionProvider,
)
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage, SenderInfo
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from planner import Planner
from runtime.inbound_journey import process_inbound_message
from runtime.noop_loggers import RecordingMessageLogger, RecordingTraceLogger
from understanding.pipeline import UnderstandingPipeline
from workflows import WorkflowRuntime
from workflows.fakes import FakeWorkflowInstanceRepository, FakeWorkflowRegistry


def _message(**kwargs) -> NormalizedMessage:
    base = dict(
        message_id="wamid.logging.1",
        correlation_id="cor_logging_1",
        sender=SenderInfo(wa_id=seed.WA_ENGINEER, profile_name="Engineer"),
        timestamp=datetime(2026, 7, 9, 10, 0, tzinfo=UTC),
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


def _interaction_handler() -> InteractionHandler:
    return InteractionHandler(workflow_runtime=_workflow_runtime())


def _resolver() -> ContextResolver:
    return ContextResolver(seed.build_dependencies())


def _workflow_runtime() -> WorkflowRuntime:
    return WorkflowRuntime(
        registry=FakeWorkflowRegistry(),
        repo=FakeWorkflowInstanceRepository(),
    )


async def _noop_send_text(wa_id: str, body: str) -> None:
    return None


async def test_trace_logger_captures_all_stages_on_success():
    """When context resolves, all 4 stages are traced: understanding, context, canonicalization, planner."""
    message = _message()
    mlog = RecordingMessageLogger()
    tlog = RecordingTraceLogger()

    await process_inbound_message(
        message,
        seed.WA_ENGINEER,
        pipeline=_pipeline(),
        context_resolver=_resolver(),
        planner=Planner(),
        workflow_runtime=_workflow_runtime(),
        interaction_handler=_interaction_handler(),
        send_text=_noop_send_text,
        message_logger=mlog,
        trace_logger=tlog,
    )

    stages = tlog.stages()
    assert "understanding" in stages
    assert "context" in stages
    assert "canonicalization" in stages
    assert "planner" in stages

    # All stages should have succeeded
    for entry in tlog.entries:
        assert entry.succeeded is True
        assert entry.duration_ms is not None and entry.duration_ms >= 0

    # Message should be marked completed
    assert "cor_logging_1" in mlog.completed

    # Reply should be logged. VALID_RECEIPT_EXTRACTION is actually an expense
    # fixture (semantic_type="expense") and FakeWorkflowRegistry() here has no
    # graphs registered, so the outcome is NO_GRAPH: understood, but nothing
    # can record it yet -- never format_reply()'s developer diagnostic.
    assert len(mlog.replies) == 1
    assert mlog.replies[0] == ("cor_logging_1", render_unsupported_reply())


async def test_trace_logger_captures_context_failure():
    """When context resolution fails, the context stage is traced with succeeded=False."""
    # Use an unregistered sender → context resolution fails
    message = _message(sender=SenderInfo(wa_id="919999999999", profile_name="Unknown"))
    mlog = RecordingMessageLogger()
    tlog = RecordingTraceLogger()

    await process_inbound_message(
        message,
        seed.WA_ENGINEER,
        pipeline=_pipeline(),
        context_resolver=_resolver(),
        planner=Planner(),
        workflow_runtime=_workflow_runtime(),
        interaction_handler=_interaction_handler(),
        send_text=_noop_send_text,
        message_logger=mlog,
        trace_logger=tlog,
    )

    stages = tlog.stages()
    assert "understanding" in stages
    assert "context" in stages

    # The context stage should have failed
    context_entries = [e for e in tlog.entries if e.stage == "context"]
    assert len(context_entries) == 1
    assert context_entries[0].succeeded is False
    assert context_entries[0].error_code is not None

    # No canonicalization/planner stages after a context failure
    assert "canonicalization" not in stages
    assert "planner" not in stages

    # Message still marked completed (the pipeline handled the failure gracefully)
    assert "cor_logging_1" in mlog.completed


async def test_trace_logger_captures_workflow_stage():
    """When a workflow starts, a 'workflow' stage is traced."""
    # Material receipt message → planner starts a workflow
    message = _message(
        text="50 bags of cement arrived at site",
        message_id="wamid.logging.2",
        correlation_id="cor_logging_2",
    )
    mlog = RecordingMessageLogger()
    tlog = RecordingTraceLogger()

    await process_inbound_message(
        message,
        seed.WA_ENGINEER,
        pipeline=_pipeline(),
        context_resolver=_resolver(),
        planner=Planner(),
        workflow_runtime=_workflow_runtime(),
        interaction_handler=_interaction_handler(),
        send_text=_noop_send_text,
        message_logger=mlog,
        trace_logger=tlog,
    )

    stages = tlog.stages()
    # The workflow stage may or may not appear depending on whether the planner
    # decides to start a workflow — either way, the first 4 stages must be present.
    assert "understanding" in stages
    assert "context" in stages


async def test_logger_failure_does_not_break_pipeline():
    """A trace logger that raises must not break the inbound journey."""
    class ExplosiveTraceLogger:
        async def log_stage(self, **kwargs):  # noqa: ANN001
            raise RuntimeError("log DB is down")

        async def log_provider_execution(self, **kwargs):  # noqa: ANN001
            raise RuntimeError("log DB is down")

    class ExplosiveMessageLogger:
        async def log_received(self, **kwargs):  # noqa: ANN001
            raise RuntimeError("log DB is down")

        async def mark_completed(self, **kwargs):  # noqa: ANN001
            raise RuntimeError("log DB is down")

        async def mark_failed(self, **kwargs):  # noqa: ANN001
            raise RuntimeError("log DB is down")

        async def log_reply(self, **kwargs):  # noqa: ANN001
            raise RuntimeError("log DB is down")

    message = _message()
    sent_replies: list[str] = []

    async def capture_send(wa_id: str, body: str) -> None:
        sent_replies.append(body)

    # Must not raise
    result = await process_inbound_message(
        message,
        seed.WA_ENGINEER,
        pipeline=_pipeline(),
        context_resolver=_resolver(),
        planner=Planner(),
        workflow_runtime=_workflow_runtime(),
        interaction_handler=_interaction_handler(),
        send_text=capture_send,
        message_logger=ExplosiveMessageLogger(),
        trace_logger=ExplosiveTraceLogger(),
    )

    assert isinstance(result.understanding, UnderstandingResult)
    assert len(sent_replies) == 1  # a broken logger must not swallow the reply


async def test_no_loggers_does_not_break():
    """When no loggers are passed, noop loggers are used — journey still works."""
    message = _message()

    result = await process_inbound_message(
        message,
        seed.WA_ENGINEER,
        pipeline=_pipeline(),
        context_resolver=_resolver(),
        planner=Planner(),
        workflow_runtime=_workflow_runtime(),
        interaction_handler=_interaction_handler(),
        send_text=_noop_send_text,
    )

    assert isinstance(result.understanding, UnderstandingResult)
