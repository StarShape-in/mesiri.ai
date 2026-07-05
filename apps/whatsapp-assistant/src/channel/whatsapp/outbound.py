"""WhatsApp outbound delivery adapter.

Transport-level sender for the WhatsApp Cloud API. This is the only place that
constructs WhatsApp API payloads. Later, the Interaction layer (M7) will drive
replies via InteractionSpec through this same adapter; for now it supports a
simple text acknowledgement.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


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

    async def send_text(self, to_wa_id: str, body: str) -> bool:
        """Send a plain text message. Returns True on success."""
        if not self.enabled:
            logger.warning("WhatsApp sender disabled (missing phone_number_id/access_token)")
            return False

        url = f"{self._graph_base_url}/{self._api_version}/{self._phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_wa_id,
            "type": "text",
            "text": {"body": body},
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

        logger.info("WhatsApp reply sent to %s", to_wa_id)
        return True
