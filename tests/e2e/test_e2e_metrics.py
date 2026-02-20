"""E2E metrics verification tests."""

from __future__ import annotations

import asyncio
import os
import re
import subprocess

import httpx
import pytest

from app.config import get_settings
from app.services.solace_subscriber import SolaceSubscriber

pytestmark = pytest.mark.e2e


def _extract_counter(metrics_text: str, metric_name: str) -> float:
    pattern = re.compile(rf"^{metric_name}(\{{[^}}]*\}})?\s+([0-9.]+)$", flags=re.MULTILINE)
    values = [float(match.group(2)) for match in pattern.finditer(metrics_text)]
    return sum(values)


@pytest.mark.asyncio
async def test_prometheus_counters_match_triggered_events(
    stripe_cli,
    solace_subscriber: SolaceSubscriber,
    clean_queues,
) -> None:
    """Validate metrics increments after triggering several events."""

    if os.getenv("RUN_E2E") != "1":
        pytest.skip("Set RUN_E2E=1 to run E2E tests")

    settings = get_settings()
    metrics_url = f"http://localhost:{settings.app_port}/metrics"

    async with httpx.AsyncClient(timeout=10) as client:
        baseline_metrics = (await client.get(metrics_url)).text
    baseline_received = _extract_counter(baseline_metrics, "stripe_webhooks_received_total")
    baseline_processed = _extract_counter(baseline_metrics, "stripe_events_processed_total")

    events = [
        "payment_intent.succeeded",
        "customer.created",
        "invoice.payment_failed",
        "checkout.session.completed",
        "charge.succeeded",
    ]

    for event in events:
        await asyncio.to_thread(subprocess.run, ["stripe", "trigger", event], check=True)

    await solace_subscriber.consume_n("stripe.all.inbound", n=5, timeout_seconds=25)

    async with httpx.AsyncClient(timeout=10) as client:
        post_metrics = (await client.get(metrics_url)).text
    post_received = _extract_counter(post_metrics, "stripe_webhooks_received_total")
    post_processed = _extract_counter(post_metrics, "stripe_events_processed_total")

    assert post_received - baseline_received >= 5
    assert post_processed - baseline_processed >= 5
