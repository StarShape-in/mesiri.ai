"""Live smoke test against a running WhatsApp ingress server."""

from __future__ import annotations

import hashlib
import hmac
import json
import sys

import httpx

from runtime.dependencies import Settings

BASE_URL = "http://127.0.0.1:8000"


def sign_payload(payload: dict, app_secret: str) -> tuple[str, bytes]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}", body


def text_payload(message_id: str = "wamid.live-test") -> dict:
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
                                    "profile": {"name": "Live Test User"},
                                }
                            ],
                            "messages": [
                                {
                                    "from": "919876543210",
                                    "id": message_id,
                                    "timestamp": "1710000000",
                                    "type": "text",
                                    "text": {"body": "Live ingress smoke test"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def main() -> int:
    settings = Settings()
    results: list[str] = []

    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        bad_verify = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "99999",
            },
        )
        results.append(f"GET bad token -> {bad_verify.status_code} (expect 403)")

        good_verify = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": settings.verify_token,
                "hub.challenge": "12345",
            },
        )
        results.append(
            f"GET good token -> {good_verify.status_code}, body={good_verify.text!r} (expect 200, '12345')"
        )

        payload = text_payload()
        signature, body = sign_payload(payload, settings.app_secret)
        good_post = client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )
        results.append(f"POST signed payload -> {good_post.status_code} (expect 200)")

        bad_post = client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid",
            },
        )
        results.append(f"POST bad signature -> {bad_post.status_code} (expect 403)")

    passed = (
        bad_verify.status_code == 403
        and good_verify.status_code == 200
        and good_verify.text == "12345"
        and good_post.status_code == 200
        and bad_post.status_code == 403
    )

    for line in results:
        print(line)

    print("RESULT:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
