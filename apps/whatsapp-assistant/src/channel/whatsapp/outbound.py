"""WhatsApp outbound delivery adapter.

Transport-level sender for the WhatsApp Cloud API. This is the only place that
constructs WhatsApp API payloads. Later, the Interaction layer (M7) will drive
replies via InteractionSpec through this same adapter; for now it supports a
simple text acknowledgement.
"""

from __future__ import annotations

import logging

import httpx

from channel.replies import ListRow

logger = logging.getLogger(__name__)

# Meta Cloud API limits for interactive list messages (verified against the
# Cloud API reference). Enforced here, at the boundary, rather than trusted
# from the caller -- a row that silently exceeds these gets truncated or
# rejected by Meta with no useful error surfaced back to the user.
_LIST_BUTTON_MAX_CHARS = 20
_LIST_ROW_TITLE_MAX_CHARS = 24
_LIST_ROW_DESCRIPTION_MAX_CHARS = 72
_LIST_MAX_ROWS = 10
_REPLY_BUTTON_TITLE_MAX_CHARS = 20
_REPLY_BUTTON_MAX_COUNT = 3


class WhatsAppSender:
    """Send messages via the Meta WhatsApp Cloud API."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        access_token: str,
        phone_number_id: str,
        api_version: str = "v21.0",
        graph_base_url: str = "https://graph.facebook.com",
    ) -> None:
        self._client = client
        self._access_token = access_token
        self._phone_number_id = phone_number_id
        self._api_version = api_version
        self._graph_base_url = graph_base_url.rstrip("/")

    @property
    def enabled(self) -> bool:
        return bool(self._access_token and self._phone_number_id)

    async def mark_as_read(self, message_id: str, *, typing_indicator: bool = True) -> bool:
        """Mark an inbound message as read (blue tick) and, optionally, show
        the "typing..." indicator until a reply is sent or ~25s elapse.

        This is the Cloud API's combined read-receipt/typing-indicator call --
        there is no separate endpoint for either. Best-effort: callers treat a
        False return the same as every other send_* failure (log and move on),
        since a missed read receipt must never block the actual reply.
        """
        if not self.enabled:
            return False

        url = f"{self._graph_base_url}/{self._api_version}/{self._phone_number_id}/messages"
        payload: dict = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        if typing_indicator:
            payload["typing_indicator"] = {"type": "text"}

        try:
            resp = await self._client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
        except httpx.HTTPError as exc:
            logger.error("WhatsApp mark_as_read failed for %s: %s", message_id, exc)
            return False

        if resp.status_code >= 400:
            logger.error(
                "WhatsApp mark_as_read rejected (%s): %s", resp.status_code, resp.text[:300]
            )
            return False
        return True

    async def send_text(self, to_wa_id: str, body: str) -> bool:
        """Send a plain text message. Returns True on success."""
        return await self._send(
            to_wa_id,
            {
                "type": "text",
                "text": {"body": body},
            },
        )

    async def send_list(
        self,
        to_wa_id: str,
        *,
        body: str,
        button_label: str,
        rows: list[ListRow],
        header: str | None = None,
        footer: str | None = None,
        section_title: str = "Options",
    ) -> bool:
        """Send a tappable WhatsApp list menu. Returns True on success.

        Payload shape and limits verified against the Cloud API reference:
        up to 10 rows total, 24-char row titles, 72-char descriptions,
        20-char button label. A row that violates these gets truncated here
        rather than silently rejected by Meta with no reply to the user.
        """
        if not rows:
            logger.error("send_list called with no rows to %s", to_wa_id)
            return False
        if len(rows) > _LIST_MAX_ROWS:
            logger.warning(
                "send_list to %s had %d rows, truncating to %d", to_wa_id, len(rows), _LIST_MAX_ROWS
            )
            rows = rows[:_LIST_MAX_ROWS]

        interactive: dict = {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": button_label[:_LIST_BUTTON_MAX_CHARS],
                "sections": [
                    {
                        "title": section_title[:_LIST_ROW_TITLE_MAX_CHARS],
                        "rows": [
                            {
                                "id": row.id,
                                "title": row.title[:_LIST_ROW_TITLE_MAX_CHARS],
                                "description": row.description[:_LIST_ROW_DESCRIPTION_MAX_CHARS],
                            }
                            for row in rows
                        ],
                    }
                ],
            },
        }
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}

        return await self._send(to_wa_id, {"type": "interactive", "interactive": interactive})

    async def send_button(
        self,
        to_wa_id: str,
        *,
        body: str,
        buttons: list[ListRow],
    ) -> bool:
        """Send up to 3 tappable quick-reply buttons (e.g. Yes/No confirmation).

        Returns True on success. Meta Cloud API limits: max 3 buttons,
        20-char titles -- enforced here rather than trusted from the caller,
        same reasoning as send_list.
        """
        if not buttons:
            logger.error("send_button called with no buttons to %s", to_wa_id)
            return False
        if len(buttons) > _REPLY_BUTTON_MAX_COUNT:
            logger.warning(
                "send_button to %s had %d buttons, truncating to %d",
                to_wa_id,
                len(buttons),
                _REPLY_BUTTON_MAX_COUNT,
            )
            buttons = buttons[:_REPLY_BUTTON_MAX_COUNT]

        interactive: dict = {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": button.id,
                            "title": button.title[:_REPLY_BUTTON_TITLE_MAX_CHARS],
                        },
                    }
                    for button in buttons
                ]
            },
        }
        return await self._send(to_wa_id, {"type": "interactive", "interactive": interactive})

    async def send_image(
        self, to_wa_id: str, image_bytes: bytes, *, caption: str | None = None
    ) -> bool:
        """Upload an image and send it. Returns True on success.

        The Cloud API has no "send these raw bytes" call -- media must be
        uploaded first (POST /{phone-number-id}/media, multipart) to get a
        media id, then referenced in the message. Two HTTP calls, not one;
        a failure at either step degrades to False rather than raising, same
        as every other send_* method here.
        """
        if not self.enabled:
            logger.warning("WhatsApp sender disabled (missing phone_number_id/access_token)")
            return False

        media_id = await self._upload_media(image_bytes, mime_type="image/png")
        if media_id is None:
            return False

        image_fields: dict = {"id": media_id}
        if caption:
            image_fields["caption"] = caption
        return await self._send(to_wa_id, {"type": "image", "image": image_fields})

    async def _upload_media(self, data: bytes, *, mime_type: str) -> str | None:
        url = f"{self._graph_base_url}/{self._api_version}/{self._phone_number_id}/media"
        try:
            resp = await self._client.post(
                url,
                data={"messaging_product": "whatsapp", "type": mime_type},
                files={"file": ("receipt.png", data, mime_type)},
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
        except httpx.HTTPError as exc:
            logger.error("WhatsApp media upload failed: %s", exc)
            return None

        if resp.status_code >= 400:
            logger.error("WhatsApp media upload rejected (%s): %s", resp.status_code, resp.text[:300])
            return None

        media_id = resp.json().get("id")
        if not media_id:
            logger.error("WhatsApp media upload response had no id: %s", resp.text[:300])
            return None
        return media_id

    async def _send(self, to_wa_id: str, message_fields: dict) -> bool:
        """POST one message to the Cloud API. `message_fields` supplies the
        `type` key and its matching payload (`text`, `interactive`, ...)."""
        if not self.enabled:
            logger.warning("WhatsApp sender disabled (missing phone_number_id/access_token)")
            return False

        url = f"{self._graph_base_url}/{self._api_version}/{self._phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_wa_id,
            **message_fields,
        }
        try:
            resp = await self._client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
        except httpx.HTTPError as exc:
            logger.error("WhatsApp send failed to %s: %s", to_wa_id, exc)
            return False

        if resp.status_code >= 400:
            logger.error("WhatsApp send rejected (%s): %s", resp.status_code, resp.text[:300])
            return False

        logger.info("WhatsApp %s sent to %s", message_fields["type"], to_wa_id)
        return True
