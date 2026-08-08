"""Unit tests for Meta webhook verification."""

from __future__ import annotations

import hashlib
import hmac

import pytest

from ingress.verification import (
    WebhookVerificationError,
    verify_request_signature,
    verify_subscription_challenge,
)


def test_verify_subscription_challenge_success() -> None:
    challenge = verify_subscription_challenge(
        hub_mode="subscribe",
        hub_verify_token="secret-token",
        hub_challenge="123456",
        expected_verify_token="secret-token",
    )
    assert challenge == "123456"


def test_verify_subscription_challenge_rejects_invalid_token() -> None:
    with pytest.raises(WebhookVerificationError):
        verify_subscription_challenge(
            hub_mode="subscribe",
            hub_verify_token="wrong",
            hub_challenge="123456",
            expected_verify_token="secret-token",
        )


def test_verify_request_signature_success() -> None:
    payload = b'{"object":"whatsapp_business_account"}'
    digest = hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
    verify_request_signature(
        payload=payload,
        signature_header=f"sha256={digest}",
        app_secret="secret",
    )


def test_verify_request_signature_rejects_invalid_signature() -> None:
    with pytest.raises(WebhookVerificationError):
        verify_request_signature(
            payload=b"{}",
            signature_header="sha256=deadbeef",
            app_secret="secret",
        )
