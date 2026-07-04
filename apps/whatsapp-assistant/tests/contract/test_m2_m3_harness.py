"""M2 -> M3 integration harness (contract level).

Drives the understanding pipeline from shared ``NormalizedMessage`` fixtures in
``scenarios/contracts/m2_to_m3/``. Today it consumes M3-authored fixtures via the
consumer-side reading model; when Alan's real M2 produces NormalizedMessage
output, the *same* fixtures/tests should accept it unchanged — that is the
integration acceptance criterion (no permanent transformation glue).

Consumer guarantee under test: every valid NormalizedMessage fixture is accepted
and yields a schema-valid UnderstandingResult carrying the inbound correlation_id.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from pydantic import ValidationError

from mesiri.infrastructure.objectstorage.fake import FakeObjectStorage
from mesiri_ai import fixtures
from mesiri_ai.fakes import FakeExtractionProvider, FakeSpeechProvider, FakeVisionProvider
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.understanding_result import UnderstandingResult
from understanding.inbound import NormalizedMessageRef
from understanding.pipeline import UnderstandingPipeline

REPO = pathlib.Path(__file__).resolve().parents[4]
FIXTURES = REPO / "scenarios" / "contracts" / "m2_to_m3"
VALID = sorted((FIXTURES / "valid").glob("*.json"))
INVALID = sorted((FIXTURES / "invalid").glob("*.json"))


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


async def _pipeline_with_media_for(msg: NormalizedMessageRef) -> UnderstandingPipeline:
    storage = FakeObjectStorage()
    if msg.media is not None:
        await storage.put_object(msg.media.object_key, b"<bytes>")
    return UnderstandingPipeline(
        speech=FakeSpeechProvider(fixtures.MALAYALAM_JCB_SPEECH),
        vision=FakeVisionProvider(fixtures.VALID_RECEIPT_VISION),
        extraction=FakeExtractionProvider(fixtures.VALID_RECEIPT_EXTRACTION),
        object_storage=storage,
    )


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_valid_fixtures_parse(path: pathlib.Path) -> None:
    msg = NormalizedMessageRef.model_validate(_load(path))
    assert msg.message_id and msg.correlation_id
    assert isinstance(msg.modality, InputModality)


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_invalid_fixtures_are_rejected(path: pathlib.Path) -> None:
    with pytest.raises(ValidationError):
        NormalizedMessageRef.model_validate(_load(path))


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
async def test_pipeline_accepts_every_valid_fixture(path: pathlib.Path) -> None:
    msg = NormalizedMessageRef.model_validate(_load(path))
    pipeline = await _pipeline_with_media_for(msg)

    result = await pipeline.understand(msg)

    # Consumer guarantees: schema-valid output + correlation propagation.
    assert isinstance(result, UnderstandingResult)
    UnderstandingResult.model_validate(result.model_dump())
    assert result.correlation_id == msg.correlation_id
    assert result.source_message_id == msg.message_id
    assert result.input_modality == msg.modality
