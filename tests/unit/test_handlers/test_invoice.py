"""Unit tests for invoice handler."""

from __future__ import annotations

from app.handlers.invoice import InvoiceHandler


def test_invoice_handler_extracts_expected_fields(load_fixture) -> None:
    """Invoice handler should include lines summary and attempt count."""

    event = load_fixture("invoice.payment_succeeded.json")
    handler = InvoiceHandler()
    envelope = handler.normalize(
        event,
        bridge_received_at="2026-02-20T14:07:00Z",
        trace_id="00000000-0000-4000-8000-000000000002",
    )

    assert envelope["data"]["id"] == "in_123"
    assert envelope["data"]["attempt_count"] == 1
    assert envelope["data"]["lines_summary"][0]["amount"] == 5000
