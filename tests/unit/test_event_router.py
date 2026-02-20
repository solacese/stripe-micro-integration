"""Unit tests for event router."""

from __future__ import annotations

import pytest

from app.services.event_router import EventRouter


@pytest.mark.parametrize(
    ("event_type", "expected"),
    [
        ("payment_intent.succeeded", "stripe/webhook/v1/payment_intent/succeeded/acct_xxx"),
        (
            "payment_intent.payment_failed",
            "stripe/webhook/v1/payment_intent/payment_failed/acct_xxx",
        ),
        ("customer.subscription.created", "stripe/webhook/v1/subscription/created/acct_xxx"),
        ("customer.subscription.updated", "stripe/webhook/v1/subscription/updated/acct_xxx"),
        ("customer.subscription.deleted", "stripe/webhook/v1/subscription/deleted/acct_xxx"),
        ("invoice.payment_succeeded", "stripe/webhook/v1/invoice/payment_succeeded/acct_xxx"),
        ("invoice.payment_failed", "stripe/webhook/v1/invoice/payment_failed/acct_xxx"),
        ("invoice.finalized", "stripe/webhook/v1/invoice/finalized/acct_xxx"),
        ("charge.succeeded", "stripe/webhook/v1/charge/succeeded/acct_xxx"),
        ("charge.failed", "stripe/webhook/v1/charge/failed/acct_xxx"),
        ("charge.dispute.created", "stripe/webhook/v1/charge/dispute/created/acct_xxx"),
        ("customer.created", "stripe/webhook/v1/customer/created/acct_xxx"),
        ("customer.deleted", "stripe/webhook/v1/customer/deleted/acct_xxx"),
        ("checkout.session.completed", "stripe/webhook/v1/checkout/session/completed/acct_xxx"),
        ("payout.failed", "stripe/webhook/v1/payout/failed/acct_xxx"),
    ],
)
def test_router_returns_expected_topics(event_type: str, expected: str) -> None:
    """Router returns exact expected topic for each supported event type."""

    router = EventRouter()
    assert router.get_topic(event_type, "acct_xxx") == expected


def test_router_falls_back_to_unroutable_topic() -> None:
    """Unknown event types map to unroutable topic segment."""

    router = EventRouter()
    assert (
        router.get_topic("something.unknown", "acct_xxx")
        == "stripe/webhook/v1/error/unroutable/acct_xxx"
    )


def test_router_always_includes_account_id_last_segment() -> None:
    """Account ID is always appended as final segment."""

    router = EventRouter()
    topic = router.get_topic("payment_intent.succeeded", "acct_custom")
    assert topic.endswith("/acct_custom")
