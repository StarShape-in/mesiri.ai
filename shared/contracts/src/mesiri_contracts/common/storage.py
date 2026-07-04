"""Object-storage port (M0).

The single interface every layer uses to reach binary media. Concrete adapters
(Cloudflare R2, in-process fake) live in ``mesiri.infrastructure`` and must be
the *only* code that touches provider SDKs, buckets, keys, or signed URLs.

Business/assistant code depends on :class:`ObjectStoragePort`, never on R2.

Ownership: SHARED ARCHITECTURE (interface). Adapters: infrastructure owner.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ObjectMetadata(BaseModel):
    """Metadata returned by ``head_object`` (no payload)."""

    key: str
    size_bytes: int = Field(ge=0)
    content_type: str | None = None
    etag: str | None = None


class StoredObject(BaseModel):
    """An object payload plus its metadata, returned by ``get_object``."""

    key: str
    data: bytes
    content_type: str | None = None

    @property
    def size_bytes(self) -> int:
        return len(self.data)


@runtime_checkable
class ObjectStoragePort(Protocol):
    """Media / object-storage capability. All methods are async."""

    async def put_object(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
    ) -> ObjectMetadata:
        ...

    async def get_object(self, key: str) -> StoredObject:
        ...

    async def head_object(self, key: str) -> ObjectMetadata:
        ...

    async def delete_object(self, key: str) -> None:
        ...

    async def generate_presigned_url(
        self,
        key: str,
        *,
        expires_in_seconds: int = 900,
        method: str = "GET",
    ) -> str:
        ...

    async def health_check(self) -> None:
        """Raise :class:`MesiriError` if the backing store is unreachable."""
        ...
