"""Unit tests for remaining event handlers."""

from __future__ import annotations

from app.handlers.charge import ChargeHandler
from app.handlers.checkout import CheckoutSessionHandler
from app.handlers.customer import CustomerHandler
from app.handlers.dispute import DisputeHandler
from app.handlers.payout import PayoutHandler


def test_charge_handler_extracts_fields(load_fixture) -> None:
    event = load_fixture("charge.succeeded.json")
    envelope = ChargeHandler().normalize(
        event,
        bridge_received_at="2026-02-20T00:00:00Z",
        trace_id="00000000-0000-4000-8000-000000000003",
    )
    assert envelope["data"]["id"] == "ch_123"
    assert envelope["data"]["risk_level"] == "normal"


def test_dispute_handler_extracts_fields(load_fixture) -> None:
    event = load_fixture("charge.dispute.created.json")
    envelope = DisputeHandler().normalize(
        event,
        bridge_received_at="2026-02-20T00:00:00Z",
        trace_id="00000000-0000-4000-8000-000000000004",
    )
    assert envelope["data"]["id"] == "dp_123"
    assert envelope["data"]["charge"] == "ch_123"


def test_customer_handler_extracts_fields(load_fixture) -> None:
    event = load_fixture("customer.created.json")
    envelope = CustomerHandler().normalize(
        event,
        bridge_received_at="2026-02-20T00:00:00Z",
        trace_id="00000000-0000-4000-8000-000000000005",
    )
    assert envelope["data"]["id"] == "cus_123"
    assert envelope["data"]["email"] == "test@example.com"


def test_checkout_handler_extracts_fields(load_fixture) -> None:
    event = load_fixture("checkout.session.completed.json")
    envelope = CheckoutSessionHandler().normalize(
        event,
        bridge_received_at="2026-02-20T00:00:00Z",
        trace_id="00000000-0000-4000-8000-000000000006",
    )
    assert envelope["data"]["id"] == "cs_123"
    assert envelope["data"]["line_items_summary"][0]["description"] == "Product A"


def test_payout_handler_extracts_fields(load_fixture) -> None:
    event = load_fixture("payout.failed.json")
    envelope = PayoutHandler().normalize(
        event,
        bridge_received_at="2026-02-20T00:00:00Z",
        trace_id="00000000-0000-4000-8000-000000000007",
    )
    assert envelope["data"]["id"] == "po_123"
    assert envelope["data"]["failure_message"] == "Bank account closed"
