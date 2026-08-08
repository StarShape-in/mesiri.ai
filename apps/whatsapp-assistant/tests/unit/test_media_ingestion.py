"""Unit tests for WhatsApp media download, including the transient-failure retry."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from ingress.media_ingestion import MetaMediaDownloader, _get_with_retry


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retry backoff is real asyncio.sleep() in production on purpose (see
    _RETRY_DELAYS_SECONDS's docstring) -- patched out here so exercising the
    retry path doesn't cost the suite ~1.2s per test."""
    import ingress.media_ingestion as module

    monkeypatch.setattr(module.asyncio, "sleep", AsyncMock())


def _response(status_code: int, *, url: str = "https://graph.example/media") -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("GET", url), json={})


@pytest.mark.asyncio
async def test_get_with_retry_returns_immediately_on_first_success() -> None:
    client = AsyncMock()
    client.get.return_value = _response(200)

    response = await _get_with_retry(client, "https://graph.example/media")

    assert response.status_code == 200
    assert client.get.await_count == 1


@pytest.mark.asyncio
async def test_get_with_retry_recovers_from_a_transient_connection_error() -> None:
    client = AsyncMock()
    client.get.side_effect = [httpx.ConnectError("connection reset"), _response(200)]

    response = await _get_with_retry(client, "https://graph.example/media")

    assert response.status_code == 200
    assert client.get.await_count == 2


@pytest.mark.asyncio
async def test_get_with_retry_recovers_from_a_transient_5xx_status() -> None:
    client = AsyncMock()
    client.get.side_effect = [_response(503), _response(200)]

    response = await _get_with_retry(client, "https://graph.example/media")

    assert response.status_code == 200
    assert client.get.await_count == 2


@pytest.mark.asyncio
async def test_get_with_retry_gives_up_after_exhausting_retries() -> None:
    client = AsyncMock()
    client.get.side_effect = httpx.ConnectError("connection reset")

    with pytest.raises(httpx.ConnectError):
        await _get_with_retry(client, "https://graph.example/media")

    # Initial attempt + 2 retries -- see _RETRY_DELAYS_SECONDS.
    assert client.get.await_count == 3


@pytest.mark.asyncio
async def test_get_with_retry_does_not_retry_a_non_transient_status() -> None:
    """A 404/401 will never succeed on retry -- retrying it only adds
    latency in front of a user waiting for a reply, for no benefit."""
    client = AsyncMock()
    client.get.return_value = _response(404)

    response = await _get_with_retry(client, "https://graph.example/media")

    assert response.status_code == 404
    assert client.get.await_count == 1


@pytest.mark.asyncio
async def test_downloader_recovers_from_one_transient_blip_per_call() -> None:
    """End-to-end through MetaMediaDownloader.download(): a single blip on
    either the metadata call or the content call must not lose the media."""
    client = AsyncMock()
    metadata_response = httpx.Response(
        200,
        request=httpx.Request("GET", "https://graph.example/v21.0/media-1"),
        json={"url": "https://cdn.example/media-1", "mime_type": "image/jpeg", "sha256": None},
    )
    content_response = httpx.Response(
        200,
        request=httpx.Request("GET", "https://cdn.example/media-1"),
        content=b"jpeg-bytes",
    )
    client.get.side_effect = [
        httpx.ConnectError("blip on metadata fetch"),
        metadata_response,
        content_response,
    ]

    downloader = MetaMediaDownloader(
        client=client,
        access_token="token",
        api_version="v21.0",
        graph_base_url="https://graph.example",
    )

    downloaded = await downloader.download("media-1")

    assert downloaded.content == b"jpeg-bytes"
    assert downloaded.mime_type == "image/jpeg"
    assert client.get.await_count == 3
