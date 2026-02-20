"""Unit tests for payment intent handler."""

from __future__ import annotations

from app.handlers.payment_intent import PaymentIntentHandler


def test_payment_intent_handler_returns_normalized_envelope(load_fixture) -> None:
    """Handler should include required envelope and normalized data fields."""

    event = load_fixture("payment_intent.succeeded.json")
    handler = PaymentIntentHandler()
    envelope = handler.normalize(
        event,
        bridge_received_at="2026-02-20T14:07:00Z",
        trace_id="00000000-0000-4000-8000-000000000000",
    )

    assert envelope["event_id"] == event["id"]
    assert envelope["event_type"] == "payment_intent.succeeded"
    assert envelope["data"]["id"] == "pi_123"
    assert envelope["raw"] == event["data"]["object"]
