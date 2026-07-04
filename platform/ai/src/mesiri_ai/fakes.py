"""Deterministic fake providers (M3).

Used by the default test suite so no path calls a paid external API. Each fake
returns a preset result or raises a preset exception, and can be given a delay to
exercise timeout handling. They implement the same ports as the real adapters.
"""

from __future__ import annotations

import asyncio

from .models import ExtractionResult, SpeechResult, VisionResult


class FakeSpeechProvider:
    def __init__(
        self,
        result: SpeechResult | None = None,
        *,
        error: BaseException | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self._result = result
        self._error = error
        self._delay = delay_seconds
        self.calls = 0

    async def transcribe(
        self, audio: bytes, *, language_hint: str | None = None, correlation_id: str | None = None
    ) -> SpeechResult:
        self.calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error is not None:
            raise self._error
        assert self._result is not None, "FakeSpeechProvider needs a result or an error"
        return self._result


class FakeVisionProvider:
    def __init__(
        self,
        result: VisionResult | None = None,
        *,
        error: BaseException | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self._result = result
        self._error = error
        self._delay = delay_seconds
        self.calls = 0

    async def analyze_image(
        self,
        image: bytes,
        *,
        mime_type: str | None = None,
        hint: str | None = None,
        correlation_id: str | None = None,
    ) -> VisionResult:
        self.calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error is not None:
            raise self._error
        assert self._result is not None, "FakeVisionProvider needs a result or an error"
        return self._result


class FakeExtractionProvider:
    def __init__(
        self,
        result: ExtractionResult | None = None,
        *,
        error: BaseException | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self._result = result
        self._error = error
        self._delay = delay_seconds
        self.calls = 0

    async def extract(
        self, text: str, *, semantic_hint: str | None = None, correlation_id: str | None = None
    ) -> ExtractionResult:
        self.calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error is not None:
            raise self._error
        assert self._result is not None, "FakeExtractionProvider needs a result or an error"
        return self._result
