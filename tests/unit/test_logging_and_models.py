"""Unit tests for logging setup and models."""

from __future__ import annotations

from app.logging import configure_logging
from app.models.solace_message import SolaceMessageMetadata
from app.models.stripe_event import StripeEventEnvelope


def test_configure_logging_runs_without_error() -> None:
    """Logging configuration should run with supported log levels."""

    configure_logging("INFO")
    configure_logging("DEBUG")


def test_models_roundtrip() -> None:
    """Pydantic models should validate expected fields."""

    envelope = StripeEventEnvelope(
        event_id="evt_1",
        event_type="payment_intent.succeeded",
        api_version="2023-10-16",
        account_id="acct_test",
        created_at=1708000000,
        bridge_received_at="2026-02-20T00:00:00Z",
        bridge_version="1.0.0",
        trace_id="00000000-0000-4000-8000-000000000008",
        data={"id": "pi_123"},
        raw={"id": "pi_123"},
    )
    metadata = SolaceMessageMetadata(
        destination="stripe/webhook/v1/payment_intent/succeeded/acct_test",
        correlation_id="evt_1",
        application_message_id="evt_1",
        properties={"stripe_api_version": "2023-10-16"},
    )

    assert envelope.event_id == "evt_1"
    assert metadata.destination is not None
