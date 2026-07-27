"""Unit tests for the WhatsApp Cloud API outbound sender.

send_list's payload shape is verified against the Cloud API reference
(interactive.type="list", action.button, action.sections[].rows[]) --
these tests pin that shape rather than re-deriving it from memory.
"""

from __future__ import annotations

import json

import httpx
import pytest

from channel.replies import ListRow
from channel.whatsapp.outbound import WhatsAppSender


def _sender(captured: list[httpx.Request]) -> WhatsAppSender:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.out.1"}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return WhatsAppSender(
        client=client,
        access_token="token",
        phone_number_id="PHONE_NUMBER_ID",
    )


@pytest.mark.asyncio
async def test_send_list_payload_matches_cloud_api_shape():
    captured: list[httpx.Request] = []
    sender = _sender(captured)

    ok = await sender.send_list(
        "919876543210",
        body="What are you reporting today?",
        button_label="Choose one",
        rows=[
            ListRow("cat_material", "Material", "Arrived or used on site"),
            ListRow("cat_expense", "Expense", "Petty cash spent"),
        ],
    )

    assert ok is True
    assert len(captured) == 1
    payload = json.loads(captured[0].content)
    assert payload["type"] == "interactive"
    assert payload["interactive"]["type"] == "list"
    assert payload["interactive"]["body"]["text"] == "What are you reporting today?"
    assert payload["interactive"]["action"]["button"] == "Choose one"
    rows = payload["interactive"]["action"]["sections"][0]["rows"]
    assert rows == [
        {"id": "cat_material", "title": "Material", "description": "Arrived or used on site"},
        {"id": "cat_expense", "title": "Expense", "description": "Petty cash spent"},
    ]


@pytest.mark.asyncio
async def test_send_list_truncates_fields_over_meta_limits():
    """Meta rejects (or silently truncates, with no reply reaching the user)
    rows over its published limits. Enforce them here instead."""
    captured: list[httpx.Request] = []
    sender = _sender(captured)

    await sender.send_list(
        "919876543210",
        body="body",
        button_label="X" * 30,  # over the 20-char button limit
        rows=[ListRow("r1", "Y" * 40, "Z" * 100)],  # over 24-char title, 72-char description
    )

    payload = json.loads(captured[0].content)
    assert payload["interactive"]["action"]["button"] == "X" * 20
    row = payload["interactive"]["action"]["sections"][0]["rows"][0]
    assert row["title"] == "Y" * 24
    assert row["description"] == "Z" * 72


@pytest.mark.asyncio
async def test_send_list_caps_at_ten_rows_total():
    captured: list[httpx.Request] = []
    sender = _sender(captured)

    await sender.send_list(
        "919876543210",
        body="body",
        button_label="Choose",
        rows=[ListRow(f"r{i}", f"Row {i}") for i in range(15)],
    )

    payload = json.loads(captured[0].content)
    assert len(payload["interactive"]["action"]["sections"][0]["rows"]) == 10


@pytest.mark.asyncio
async def test_send_list_with_no_rows_does_not_send():
    captured: list[httpx.Request] = []
    sender = _sender(captured)

    ok = await sender.send_list("919876543210", body="body", button_label="Choose", rows=[])

    assert ok is False
    assert captured == []


@pytest.mark.asyncio
async def test_send_text_still_sends_plain_text_shape():
    """send_list must not have disturbed the existing send_text behavior."""
    captured: list[httpx.Request] = []
    sender = _sender(captured)

    ok = await sender.send_text("919876543210", "Recorded. Thank you.")

    assert ok is True
    payload = json.loads(captured[0].content)
    assert payload["type"] == "text"
    assert payload["text"]["body"] == "Recorded. Thank you."


# --- #11 Reply Workflow: wamid capture -------------------------------------


@pytest.mark.asyncio
async def test_send_text_capturing_id_returns_metas_wamid():
    captured: list[httpx.Request] = []
    sender = _sender(captured)

    wamid = await sender.send_text_capturing_id("919876543210", "Recorded. Thank you.")

    assert wamid == "wamid.out.1"


@pytest.mark.asyncio
async def test_send_text_still_returns_bool_true_on_success():
    """send_text's own contract (bool) must be unchanged now that _send
    returns str | None internally."""
    captured: list[httpx.Request] = []
    sender = _sender(captured)

    result = await sender.send_text("919876543210", "hi")
    assert result is True
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_send_text_capturing_id_returns_none_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    sender = WhatsAppSender(client=client, access_token="token", phone_number_id="PHONE_NUMBER_ID")

    wamid = await sender.send_text_capturing_id("919876543210", "hi")
    assert wamid is None


@pytest.mark.asyncio
async def test_send_text_capturing_id_returns_none_when_disabled():
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    sender = WhatsAppSender(client=client, access_token="", phone_number_id="")

    wamid = await sender.send_text_capturing_id("919876543210", "hi")
    assert wamid is None


@pytest.mark.asyncio
async def test_send_text_capturing_id_degrades_to_none_on_malformed_response():
    """Meta responding 200 with no parseable messages[0].id must not raise --
    the send itself succeeded, there's just nothing to record for later
    reply resolution."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"messaging_product": "whatsapp"})  # no "messages" key

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    sender = WhatsAppSender(client=client, access_token="token", phone_number_id="PHONE_NUMBER_ID")

    wamid = await sender.send_text_capturing_id("919876543210", "hi")
    assert wamid is None


@pytest.mark.asyncio
async def test_send_list_and_send_button_bool_contract_unchanged_by_str_refactor():
    """send_list/send_button return bool, not the raw _send result -- pins
    the (await self._send(...)) is not None wrapping added alongside
    send_text_capturing_id."""
    captured: list[httpx.Request] = []
    sender = _sender(captured)

    result = await sender.send_list(
        "919876543210", body="b", button_label="Choose", rows=[ListRow("r1", "Row 1")]
    )
    assert result is True
    assert isinstance(result, bool)
