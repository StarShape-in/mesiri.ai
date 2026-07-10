"""Speech-understanding provider port (M3).

A single operation returns transcript + detected language + translation, because
the intended provider (Sarvam) delivers all three from one model invocation.
Callers depend on this protocol, never on a provider SDK.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import SpeechResult


@runtime_checkable
class SpeechUnderstandingProvider(Protocol):
    async def transcribe(
        self,
        audio: bytes,
        *,
        language_hint: str | None = None,
        correlation_id: str | None = None,
    ) -> SpeechResult: ...
