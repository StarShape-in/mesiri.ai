"""Unit tests for WhatsApp webhook HTTP endpoints."""

from __future__ import annotations

import pytest
from tests.conftest import sign_payload
from tests.fixtures.meta_payloads import text_webhook_payload


@pytest.mark.asyncio
async def test_get_webhook_verification(client) -> None:
    response = await client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test-verify-token",
            "hub.challenge": "123456",
        },
    )

    assert response.status_code == 200
    assert response.text == "123456"


@pytest.mark.asyncio
async def test_post_webhook_returns_200_and_persists_text_message(client, app) -> None:
    payload = text_webhook_payload()
    signature, body = sign_payload(payload, "test-app-secret")

    response = await client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200

    container = app.state.container
    await container.receiver.wait_until_idle()
    normalized = await container.message_store.get("wamid.text")
    assert normalized is not None
    assert normalized.text == "Installed 20 bags of cement"


@pytest.mark.asyncio
async def test_post_webhook_rejects_invalid_signature(client) -> None:
    payload = text_webhook_payload()
    _, body = sign_payload(payload, "test-app-secret")

    response = await client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=invalid",
        },
    )

    assert response.status_code == 403
