"""E2E reconnect behavior tests."""

from __future__ import annotations

import asyncio
import os
import subprocess
import time

import httpx
import pytest

from app.config import get_settings
from app.services.solace_subscriber import SolaceSubscriber

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_bridge_reconnects_after_broker_restart(
    stripe_cli,
    solace_subscriber: SolaceSubscriber,
    clean_queues,
) -> None:
    """Restart local broker and verify bridge recovers with buffered events."""

    if os.getenv("RUN_E2E") != "1":
        pytest.skip("Set RUN_E2E=1 to run E2E tests")
    if os.getenv("RUN_E2E_LOCAL") != "1":
        pytest.skip("Reconnect scenario requires local Docker Solace")

    settings = get_settings()
    base_url = f"http://localhost:{settings.app_port}"

    await asyncio.to_thread(
        subprocess.run,
        ["stripe", "trigger", "payment_intent.succeeded"],
        check=True,
    )
    msg_before = await solace_subscriber.consume_one("stripe.payments.inbound", timeout_seconds=10)
    assert msg_before is not None

    await asyncio.to_thread(
        subprocess.run,
        ["docker", "restart", "stripe-solace-bridge-solace-1"],
        check=True,
    )

    offline_deadline = time.time() + 120
    async with httpx.AsyncClient(timeout=3) as client:
        while time.time() < offline_deadline:
            status = (await client.get(f"{base_url}/ready")).status_code
            if status == 503:
                break
            await asyncio.sleep(2)

    await asyncio.to_thread(
        subprocess.run,
        ["stripe", "trigger", "payment_intent.succeeded"],
        check=True,
    )

    online_deadline = time.time() + 300
    async with httpx.AsyncClient(timeout=3) as client:
        while time.time() < online_deadline:
            status = (await client.get(f"{base_url}/ready")).status_code
            if status == 200:
                break
            await asyncio.sleep(2)

    msg_after = await solace_subscriber.consume_one("stripe.payments.inbound", timeout_seconds=30)
    assert msg_after is not None
