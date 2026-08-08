"""Verify Meta WhatsApp webhook subscription challenges and request authenticity."""

from __future__ import annotations

import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "X-Hub-Signature-256"
SIGNATURE_PREFIX = "sha256="


class WebhookVerificationError(Exception):
    """Raised when a webhook request fails verification."""


def verify_subscription_challenge(
    *,
    hub_mode: str | None,
    hub_verify_token: str | None,
    hub_challenge: str | None,
    expected_verify_token: str,
) -> str:
    """Validate Meta webhook subscription challenge and return the challenge value."""
    if hub_mode != "subscribe":
        logger.warning("Rejected webhook challenge with unsupported hub.mode=%s", hub_mode)
        raise WebhookVerificationError("Unsupported hub.mode")

    if not hub_verify_token or not hmac.compare_digest(hub_verify_token, expected_verify_token):
        logger.warning("Rejected webhook challenge due to verify token mismatch")
        raise WebhookVerificationError("Invalid verify token")

    if not hub_challenge:
        logger.warning("Rejected webhook challenge without hub.challenge")
        raise WebhookVerificationError("Missing hub.challenge")

    return hub_challenge


def verify_request_signature(
    *,
    payload: bytes,
    signature_header: str | None,
    app_secret: str,
) -> None:
    """Validate Meta webhook payload signature using the app secret."""
    if not app_secret:
        logger.error("Webhook signature verification failed: app secret not configured")
        raise WebhookVerificationError("App secret not configured")

    if not signature_header:
        logger.warning("Rejected webhook request without signature header")
        raise WebhookVerificationError("Missing signature header")

    if not signature_header.startswith(SIGNATURE_PREFIX):
        logger.warning("Rejected webhook request with invalid signature format")
        raise WebhookVerificationError("Invalid signature format")

    received_signature = signature_header[len(SIGNATURE_PREFIX) :]
    expected_signature = hmac.new(
        app_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(received_signature, expected_signature):
        logger.warning("Rejected webhook request due to signature mismatch")
        raise WebhookVerificationError("Invalid signature")
