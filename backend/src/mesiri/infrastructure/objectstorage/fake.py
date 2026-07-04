"""In-process fake object storage (M1).

Implements :class:`ObjectStoragePort` against an in-memory dict. Used for local
development (R2 is not meaningfully emulable locally) and for the default test
suite, so no code path depends on the R2 SDK during normal runs.

``fail_health`` lets tests simulate an unreachable store for readiness checks.
"""

from __future__ import annotations

from mesiri_contracts.common.errors import ErrorCategory, ErrorCode, MesiriError
from mesiri_contracts.common.storage import ObjectMetadata, StoredObject


class FakeObjectStorage:
    name = "object_storage"
    required = True

    def __init__(self, *, fail_health: bool = False) -> None:
        self._store: dict[str, tuple[bytes, str | None]] = {}
        self.fail_health = fail_health

    async def put_object(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> ObjectMetadata:
        self._store[key] = (bytes(data), content_type)
        return ObjectMetadata(key=key, size_bytes=len(data), content_type=content_type)

    async def get_object(self, key: str) -> StoredObject:
        if key not in self._store:
            raise MesiriError(
                error_code=ErrorCode.OBJECT_STORAGE_UNAVAILABLE.value,
                category=ErrorCategory.NOT_FOUND,
                retryable=False,
                user_safe_message="The requested media could not be found.",
                internal_message=f"object not found: {key}",
            )
        data, content_type = self._store[key]
        return StoredObject(key=key, data=data, content_type=content_type)

    async def head_object(self, key: str) -> ObjectMetadata:
        obj = await self.get_object(key)
        return ObjectMetadata(key=key, size_bytes=obj.size_bytes, content_type=obj.content_type)

    async def delete_object(self, key: str) -> None:
        self._store.pop(key, None)

    async def generate_presigned_url(
        self, key: str, *, expires_in_seconds: int = 900, method: str = "GET"
    ) -> str:
        return f"memory://{key}?expires_in={expires_in_seconds}&method={method}"

    async def check_health(self) -> None:
        if self.fail_health:
            raise MesiriError.dependency_unavailable(
                "object_storage",
                code=ErrorCode.OBJECT_STORAGE_UNAVAILABLE.value,
                internal_message="fake object storage marked unhealthy",
            )

    # Alias for the port's health_check name.
    async def health_check(self) -> None:
        await self.check_health()
