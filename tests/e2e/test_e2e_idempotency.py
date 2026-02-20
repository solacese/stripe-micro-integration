"""E2E idempotency tests."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.services.solace_subscriber import SolaceSubscriber

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_duplicate_event_produces_one_message(
    solace_subscriber: SolaceSubscriber,
    clean_queues,
    load_fixture,
) -> None:
    """Posting same signed event twice should emit one queue message only."""

    if os.getenv("RUN_E2E") != "1":
        pytest.skip("Set RUN_E2E=1 to run E2E tests")

    settings = get_settings()
    event = load_fixture("payment_intent.succeeded.json")
    event["id"] = "evt_duplicate_test"
    payload = json.dumps(event).encode("utf-8")

    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode()
    sig = hmac.new(
        settings.stripe_webhook_secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    signature = f"t={timestamp},v1={sig}"

    async with AsyncClient(base_url=f"http://localhost:{settings.app_port}") as client:
        first = await client.post(
            "/webhooks/stripe",
            content=payload,
            headers={"Stripe-Signature": signature},
        )
        second = await client.post(
            "/webhooks/stripe",
            content=payload,
            headers={"Stripe-Signature": signature},
        )

    assert first.status_code == 200
    assert second.status_code == 200

    messages = await solace_subscriber.consume_n("stripe.payments.inbound", n=5, timeout_seconds=5)
    filtered = [m for m in messages if m.get("event_id") == "evt_duplicate_test"]
    assert len(filtered) == 1
