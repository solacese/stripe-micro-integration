"""Unit tests for subscription handler."""

from __future__ import annotations

from app.handlers.subscription import SubscriptionHandler


def test_subscription_handler_extracts_expected_fields(load_fixture) -> None:
    """Subscription handler should extract normalization fields."""

    event = load_fixture("customer.subscription.created.json")
    handler = SubscriptionHandler()
    envelope = handler.normalize(
        event,
        bridge_received_at="2026-02-20T14:07:00Z",
        trace_id="00000000-0000-4000-8000-000000000001",
    )

    assert envelope["data"]["id"] == "sub_123"
    assert envelope["data"]["customer"] == "cus_123"
    assert isinstance(envelope["data"]["items"], list)
