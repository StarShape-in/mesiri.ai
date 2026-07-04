"""Sample Meta webhook payloads for ingress tests."""

from __future__ import annotations

from typing import Any


def text_webhook_payload(*, message_id: str = "wamid.text") -> dict[str, Any]:
    """Build a sample Meta text message webhook payload."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550001111",
                                "phone_number_id": "PHONE_NUMBER_ID",
                            },
                            "contacts": [
                                {
                                    "wa_id": "919876543210",
                                    "profile": {"name": "Site Engineer"},
                                }
                            ],
                            "messages": [
                                {
                                    "from": "919876543210",
                                    "id": message_id,
                                    "timestamp": "1710000000",
                                    "type": "text",
                                    "text": {"body": "Installed 20 bags of cement"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def image_webhook_payload(*, message_id: str = "wamid.image") -> dict[str, Any]:
    """Build a sample Meta image message webhook payload."""
    payload = text_webhook_payload(message_id=message_id)
    payload["entry"][0]["changes"][0]["value"]["messages"] = [
        {
            "from": "919876543210",
            "id": message_id,
            "timestamp": "1710000001",
            "type": "image",
            "image": {
                "id": "media-image-1",
                "mime_type": "image/jpeg",
                "caption": "Delivery challan",
            },
        }
    ]
    return payload


def voice_webhook_payload(*, message_id: str = "wamid.voice") -> dict[str, Any]:
    """Build a sample Meta voice message webhook payload."""
    payload = text_webhook_payload(message_id=message_id)
    payload["entry"][0]["changes"][0]["value"]["messages"] = [
        {
            "from": "919876543210",
            "id": message_id,
            "timestamp": "1710000002",
            "type": "audio",
            "audio": {
                "id": "media-audio-1",
                "mime_type": "audio/ogg; codecs=opus",
                "voice": True,
            },
        }
    ]
    return payload
