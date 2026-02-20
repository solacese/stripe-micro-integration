"""Integration test for Solace publish/consume roundtrip."""

from __future__ import annotations

import os
import uuid

import pytest

from app.config import get_settings
from app.services.solace_publisher import SolacePublisher
from app.services.solace_subscriber import SolaceSubscriber

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("RUN_SOLACE_INTEGRATION") != "1",
    reason="Set RUN_SOLACE_INTEGRATION=1 to run Solace roundtrip integration test",
)
@pytest.mark.asyncio
async def test_solace_roundtrip() -> None:
    """Publish to topic and consume from audit queue to validate message integrity."""

    settings = get_settings()
    publisher = SolacePublisher(settings)
    subscriber = SolaceSubscriber(settings)

    await publisher.connect()
    await subscriber.connect()

    event_id = f"evt_roundtrip_{uuid.uuid4().hex}"
    account_id = settings.e2e_stripe_account_id or "acct_test"
    topic = f"stripe/webhook/v1/payment_intent/succeeded/{account_id}"
    payload = {
        "event_id": event_id,
        "event_type": "payment_intent.succeeded",
        "api_version": "2023-10-16",
        "account_id": account_id,
        "created_at": 1708000000,
        "bridge_received_at": "2026-02-20T00:00:00Z",
        "bridge_version": "1.0.0",
        "trace_id": str(uuid.uuid4()),
        "data": {"id": "pi_test"},
        "raw": {"id": "pi_test"},
    }

    await publisher.publish(topic, payload, event_id)
    message = await subscriber.consume_one(
        "stripe.all.inbound",
        timeout_seconds=5,
        include_meta=True,
    )

    assert message is not None
    assert message["event_id"] == event_id
    assert message["event_type"] == "payment_intent.succeeded"

    await subscriber.disconnect()
    await publisher.disconnect()
