"""E2E dead-message-queue behavior tests."""

from __future__ import annotations

import os
import uuid

import pytest
from solace.messaging.config.message_acknowledgement_configuration import Outcome
from solace.messaging.config.missing_resources_creation_configuration import (
    MissingResourcesCreationStrategy,
)
from solace.messaging.resources.queue import Queue

from app.config import get_settings
from app.services.solace_publisher import SolacePublisher
from app.services.solace_subscriber import SolaceSubscriber

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_poison_message_lands_on_dmq(
    solace_subscriber: SolaceSubscriber,
    clean_queues,
) -> None:
    """Malformed payload repeatedly rejected should eventually route to DMQ."""

    if os.getenv("RUN_E2E") != "1":
        pytest.skip("Set RUN_E2E=1 to run E2E tests")

    settings = get_settings()
    publisher = SolacePublisher(settings)
    await publisher.connect()

    event_id = f"evt_poison_{uuid.uuid4().hex}"
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
        "data": {"raw": "not-json-consumer"},
        "raw": {"raw": "not-json-consumer"},
    }
    await publisher.publish(topic, payload, event_id)

    await solace_subscriber.connect()
    service = solace_subscriber._messaging_service
    assert service is not None

    receiver = (
        service.create_persistent_message_receiver_builder()
        .with_message_client_acknowledgement()
        .with_missing_resources_creation_strategy(MissingResourcesCreationStrategy.DO_NOT_CREATE)
        .build(Queue.durable_non_exclusive_queue("stripe.payments.inbound"))
    )

    try:
        receiver.start()
        for _ in range(6):
            inbound = receiver.receive_message(timeout=2000)
            if inbound is None:
                break
            receiver.settle(inbound, Outcome.FAILED)
    finally:
        receiver.terminate()

    dmq_message = await solace_subscriber.consume_one("stripe.errors.dmq", timeout_seconds=20)
    assert dmq_message is not None

    await publisher.disconnect()
