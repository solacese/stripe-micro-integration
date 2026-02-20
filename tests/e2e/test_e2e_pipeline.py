"""E2E tests for Stripe trigger to Solace queue delivery."""

from __future__ import annotations

import asyncio
import os
import subprocess
from datetime import datetime
from uuid import UUID

import pytest

from app.config import get_settings
from app.services.solace_subscriber import SolaceSubscriber

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize(
    ("event_type", "expected_queue"),
    [
        ("payment_intent.succeeded", "stripe.payments.inbound"),
        ("payment_intent.payment_failed", "stripe.payments.inbound"),
        ("customer.subscription.created", "stripe.subscriptions.inbound"),
        ("customer.subscription.updated", "stripe.subscriptions.inbound"),
        ("customer.subscription.deleted", "stripe.subscriptions.inbound"),
        ("invoice.payment_succeeded", "stripe.invoices.inbound"),
        ("invoice.payment_failed", "stripe.invoices.inbound"),
        ("customer.created", "stripe.customers.inbound"),
        ("customer.deleted", "stripe.customers.inbound"),
        ("charge.succeeded", "stripe.all.inbound"),
        ("checkout.session.completed", "stripe.all.inbound"),
    ],
)
@pytest.mark.asyncio
async def test_event_flows_to_correct_queue(
    event_type: str,
    expected_queue: str,
    stripe_cli,
    solace_subscriber: SolaceSubscriber,
    clean_queues,
) -> None:
    """Trigger Stripe event and assert delivery to expected queue."""

    if os.getenv("RUN_E2E") != "1":
        pytest.skip("Set RUN_E2E=1 to run E2E tests")

    settings = get_settings()
    await asyncio.to_thread(subprocess.run, ["stripe", "trigger", event_type], check=True)

    message = await solace_subscriber.consume_one(
        expected_queue,
        timeout_seconds=settings.e2e_consume_timeout_seconds,
    )
    assert message is not None
    assert message["event_type"] == event_type
    assert message.get("account_id")
    datetime.fromisoformat(message["bridge_received_at"].replace("Z", "+00:00"))
    UUID(message["trace_id"])


@pytest.mark.asyncio
async def test_all_events_also_land_on_audit_queue(
    stripe_cli,
    solace_subscriber: SolaceSubscriber,
) -> None:
    """Trigger multiple events and ensure they all appear on audit queue."""

    if os.getenv("RUN_E2E") != "1":
        pytest.skip("Set RUN_E2E=1 to run E2E tests")

    triggers = ["payment_intent.succeeded", "customer.created", "invoice.payment_failed"]
    for event in triggers:
        await asyncio.to_thread(subprocess.run, ["stripe", "trigger", event], check=True)

    messages = await solace_subscriber.consume_n("stripe.all.inbound", n=3, timeout_seconds=15)
    assert len(messages) == 3
    event_types = [msg["event_type"] for msg in messages]
    assert event_types == triggers


@pytest.mark.asyncio
async def test_message_user_properties(
    stripe_cli,
    solace_subscriber: SolaceSubscriber,
    clean_queues,
) -> None:
    """Validate Solace metadata and user properties are set as expected."""

    if os.getenv("RUN_E2E") != "1":
        pytest.skip("Set RUN_E2E=1 to run E2E tests")

    await asyncio.to_thread(
        subprocess.run,
        ["stripe", "trigger", "payment_intent.succeeded"],
        check=True,
    )
    message = await solace_subscriber.consume_one(
        "stripe.payments.inbound",
        timeout_seconds=10,
        include_meta=True,
    )
    assert message is not None
    meta = message["_solace_meta"]
    assert meta["correlation_id"] == message["event_id"]
    assert meta["application_message_id"] == message["event_id"]
    props = meta["properties"]
    assert "stripe_api_version" in props
    assert "stripe_account_id" in props
    assert "event_created_at" in props
    assert "bridge_received_at" in props
