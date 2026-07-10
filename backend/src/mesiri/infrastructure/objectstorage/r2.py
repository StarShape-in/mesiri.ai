"""Cloudflare R2 object-storage adapter (M1).

R2 is S3-compatible, so this uses boto3's S3 client against R2's endpoint. boto3
is imported lazily and runs in a thread (it is a synchronous SDK) so the rest of
the runtime stays async and boto3 is only required for the ``r2`` lane.

This is the only module that knows about buckets, keys, signed URLs, or the SDK.
"""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

from mesiri_contracts.common.storage import ObjectMetadata, StoredObject

from ...bootstrap.settings import ObjectStorageSettings
from ..errors import map_object_storage_error


class R2ObjectStorage:
    name = "object_storage"
    required = True

    def __init__(self, settings: ObjectStorageSettings) -> None:
        self._settings = settings
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            import boto3  # lazy: only needed for the r2 lane

            s = self._settings
            self._client = boto3.client(
                "s3",
                endpoint_url=s.endpoint_url,
                aws_access_key_id=s.access_key_id.get_secret_value() if s.access_key_id else None,
                aws_secret_access_key=(
                    s.secret_access_key.get_secret_value() if s.secret_access_key else None
                ),
                region_name=s.region,
            )
        return self._client

    async def _call(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return await asyncio.to_thread(partial(fn, *args, **kwargs))
        except Exception as exc:  # noqa: BLE001 — mapped to the shared contract
            raise map_object_storage_error(exc) from exc

    async def put_object(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> ObjectMetadata:
        client = self._get_client()
        extra = {"ContentType": content_type} if content_type else {}
        await self._call(
            client.put_object, Bucket=self._settings.bucket, Key=key, Body=data, **extra
        )
        return ObjectMetadata(key=key, size_bytes=len(data), content_type=content_type)

    async def get_object(self, key: str) -> StoredObject:
        client = self._get_client()
        resp = await self._call(client.get_object, Bucket=self._settings.bucket, Key=key)
        body = await asyncio.to_thread(resp["Body"].read)
        return StoredObject(key=key, data=body, content_type=resp.get("ContentType"))

    async def head_object(self, key: str) -> ObjectMetadata:
        client = self._get_client()
        resp = await self._call(client.head_object, Bucket=self._settings.bucket, Key=key)
        return ObjectMetadata(
            key=key,
            size_bytes=int(resp.get("ContentLength", 0)),
            content_type=resp.get("ContentType"),
            etag=resp.get("ETag"),
        )

    async def delete_object(self, key: str) -> None:
        client = self._get_client()
        await self._call(client.delete_object, Bucket=self._settings.bucket, Key=key)

    async def generate_presigned_url(
        self, key: str, *, expires_in_seconds: int = 900, method: str = "GET"
    ) -> str:
        client = self._get_client()
        op = "get_object" if method.upper() == "GET" else "put_object"
        return await self._call(
            client.generate_presigned_url,
            op,
            Params={"Bucket": self._settings.bucket, "Key": key},
            ExpiresIn=expires_in_seconds,
        )

    async def check_health(self) -> None:
        client = self._get_client()
        await self._call(client.head_bucket, Bucket=self._settings.bucket)

    async def health_check(self) -> None:
        await self.check_health()
