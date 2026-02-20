"""Unit tests for Stripe webhook verifier."""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest

from app.services.stripe_verifier import StripeVerifier, WebhookVerificationError


def _sign_payload(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    ts = timestamp or int(time.time())
    signed_payload = f"{ts}.{payload.decode('utf-8')}".encode()
    digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def test_valid_signature_parses_event_correctly(load_fixture) -> None:
    """Valid signature should parse into event dict."""

    event = load_fixture("payment_intent.succeeded.json")
    payload = json.dumps(event).encode("utf-8")
    secret = "whsec_test_secret"
    signature = _sign_payload(payload, secret)

    verifier = StripeVerifier(secret)
    parsed = verifier.verify(payload, signature)

    assert parsed["id"] == event["id"]
    assert parsed["type"] == event["type"]


def test_tampered_body_raises_error(load_fixture) -> None:
    """Tampering body after signing should fail verification."""

    event = load_fixture("payment_intent.succeeded.json")
    payload = json.dumps(event).encode("utf-8")
    secret = "whsec_test_secret"
    signature = _sign_payload(payload, secret)
    tampered = payload + b" "

    verifier = StripeVerifier(secret)

    with pytest.raises(WebhookVerificationError):
        verifier.verify(tampered, signature)


def test_missing_signature_header_raises_error(load_fixture) -> None:
    """Missing signature header should fail validation."""

    payload = json.dumps(load_fixture("payment_intent.succeeded.json")).encode("utf-8")
    verifier = StripeVerifier("whsec_test")

    with pytest.raises(WebhookVerificationError, match="Missing Stripe-Signature"):
        verifier.verify(payload, None)


def test_timestamp_outside_tolerance_raises_error(load_fixture) -> None:
    """Old timestamps should fail Stripe verification tolerance check."""

    event = load_fixture("payment_intent.succeeded.json")
    payload = json.dumps(event).encode("utf-8")
    secret = "whsec_test_secret"
    old_timestamp = int(time.time()) - 3600
    signature = _sign_payload(payload, secret, timestamp=old_timestamp)

    verifier = StripeVerifier(secret)

    with pytest.raises(WebhookVerificationError):
        verifier.verify(payload, signature)
