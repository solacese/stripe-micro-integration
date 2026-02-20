"""End-to-end fixtures for full pipeline tests."""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
from collections.abc import AsyncIterator, Iterator

import pytest

from app.config import get_settings
from app.services.solace_subscriber import SolaceSubscriber

pytestmark = pytest.mark.e2e


def _require_e2e_enabled() -> None:
    if os.getenv("RUN_E2E") != "1":
        pytest.skip("Set RUN_E2E=1 to run E2E tests")


@pytest.fixture(scope="session")
def stripe_cli() -> Iterator[subprocess.Popen[str]]:
    """Start Stripe CLI listener and expose webhook secret through environment."""

    _require_e2e_enabled()

    settings = get_settings()
    cmd = [
        "stripe",
        "listen",
        "--api-key",
        settings.stripe_api_key,
        "--forward-to",
        f"http://localhost:{settings.app_port}/webhooks/stripe",
    ]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    assert process.stdout is not None
    secret_pattern = re.compile(r"whsec_[a-zA-Z0-9]+")
    webhook_secret: str | None = None

    for _ in range(50):
        line = process.stdout.readline().strip()
        match = secret_pattern.search(line)
        if match:
            webhook_secret = match.group(0)
            break

    if webhook_secret:
        os.environ["STRIPE_WEBHOOK_SECRET"] = webhook_secret

    yield process

    process.terminate()
    process.wait(timeout=10)


@pytest.fixture(scope="session")
async def solace_subscriber() -> AsyncIterator[SolaceSubscriber]:
    """Provide connected Solace subscriber for E2E validation."""

    _require_e2e_enabled()

    subscriber = SolaceSubscriber(get_settings())
    await subscriber.connect()
    yield subscriber
    await subscriber.disconnect()


@pytest.fixture(scope="function")
async def clean_queues(solace_subscriber: SolaceSubscriber) -> dict[str, int]:
    """Drain queues before each test when enabled."""

    settings = get_settings()
    if not settings.e2e_queue_drain_before_test:
        return {}

    queues = [
        "stripe.payments.inbound",
        "stripe.subscriptions.inbound",
        "stripe.invoices.inbound",
        "stripe.customers.inbound",
        "stripe.all.inbound",
        "stripe.errors.dmq",
    ]

    drained: dict[str, int] = {}
    for queue in queues:
        drained[queue] = await solace_subscriber.drain_queue(queue)

    await asyncio.sleep(0.1)
    return drained
