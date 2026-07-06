"""Replay a captured Meta webhook POST twice to verify idempotency."""

from __future__ import annotations

import base64
import json
import re
import sys

import httpx

from runtime.dependencies import Settings

NGROK_REQUEST_ID = "airt_3G2a93nczWYhQ2TaMcHoKErJK6j"
BASE_URL = "http://127.0.0.1:8000"


def load_captured_request() -> tuple[bytes, str]:
    """Load exact body and signature from ngrok request inspection API."""
    response = httpx.get(
        f"http://127.0.0.1:4040/api/requests/http/{NGROK_REQUEST_ID}",
        timeout=10.0,
    )
    response.raise_for_status()
    detail = response.json()

    raw_request = base64.b64decode(detail["request"]["raw"])
    header_block, body = raw_request.split(b"\r\n\r\n", 1)
    headers_text = header_block.decode("utf-8", errors="replace")

    signature_match = re.search(
        r"X-Hub-Signature-256:\s*(sha256=[0-9a-f]+)",
        headers_text,
        re.IGNORECASE,
    )
    if not signature_match:
        raise RuntimeError("Captured request is missing X-Hub-Signature-256 header")

    return body, signature_match.group(1)


def extract_message_id(body: bytes) -> str:
    payload = json.loads(body)
    return payload["entry"][0]["changes"][0]["value"]["messages"][0]["id"]


def main() -> int:
    Settings()
    body, signature = load_captured_request()
    message_id = extract_message_id(body)

    print(f"Captured message_id: {message_id}")
    print(f"Body bytes: {len(body)}")

    results: list[int] = []
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        for attempt in (1, 2):
            response = client.post(
                "/webhook",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": signature,
                },
            )
            results.append(response.status_code)
            print(f"Replay attempt {attempt}: HTTP {response.status_code}")

    passed = results == [200, 200]
    print("RESULT:", "PASS" if passed else "FAIL")
    print(
        "Check server logs for:",
        f"Duplicate WhatsApp message ignored: {message_id}",
    )
    print("Second replay must NOT log a second Persisted normalized WhatsApp message.")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
