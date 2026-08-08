"""Vision-understanding provider port (M3).

Image understanding: document classification + semantic description + best-effort
raw field extraction (e.g. receipt line items). Callers depend on this protocol,
never on a provider SDK.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import VisionResult


@runtime_checkable
class VisionUnderstandingProvider(Protocol):
    async def analyze_image(
        self,
        image: bytes,
        *,
        mime_type: str | None = None,
        hint: str | None = None,
        correlation_id: str | None = None,
    ) -> VisionResult: ...
