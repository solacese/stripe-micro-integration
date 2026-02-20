"""Unit tests for app factory and core endpoints."""

from __future__ import annotations

from time import monotonic

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.services.stripe_verifier import WebhookVerificationError


class _FakeVerifier:
    def __init__(self, event: dict[str, object], fail: bool = False) -> None:
        self._event = event
        self._fail = fail

    def verify(self, payload: bytes, signature_header: str | None) -> dict[str, object]:
        if self._fail:
            raise WebhookVerificationError("bad signature")
        return self._event


class _FakeProcessor:
    def __init__(self, accept: bool = True) -> None:
        self._accept = accept
        self.events: list[dict[str, object]] = []

    def enqueue(self, event: dict[str, object]) -> bool:
        self.events.append(event)
        return self._accept


class _FakePublisherState:
    def __init__(self, connected: bool) -> None:
        self.is_connected = connected


@pytest.mark.asyncio
async def test_health_ready_and_metrics_endpoints(make_settings) -> None:
    """App should expose health, ready, and metrics endpoints."""

    app = create_app(make_settings())
    app.state.started_at = monotonic() - 1.0
    app.state.solace_publisher = _FakePublisherState(connected=True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        health = await client.get("/health")
        ready = await client.get("/ready")
        metrics = await client.get("/metrics")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code == 200
    assert "stripe_webhooks_received_total" in metrics.text


@pytest.mark.asyncio
async def test_ready_returns_503_when_disconnected(make_settings) -> None:
    """Readiness should fail when Solace publisher is disconnected."""

    app = create_app(make_settings())
    app.state.started_at = monotonic()
    app.state.solace_publisher = _FakePublisherState(connected=False)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        ready = await client.get("/ready")

    assert ready.status_code == 503


@pytest.mark.asyncio
async def test_webhook_success_and_failure_paths(make_settings, load_fixture) -> None:
    """Webhook should return 200 on success and 400 on verification failure."""

    app = create_app(make_settings())
    app.state.started_at = monotonic()
    app.state.solace_publisher = _FakePublisherState(connected=True)

    event = load_fixture("customer.created.json")
    app.state.stripe_verifier = _FakeVerifier(event, fail=False)
    processor = _FakeProcessor(accept=True)
    app.state.async_processor = processor

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        ok = await client.post(
            "/webhooks/stripe",
            content=b"{}",
            headers={"Stripe-Signature": "sig"},
        )

    assert ok.status_code == 200
    assert len(processor.events) == 1

    app.state.stripe_verifier = _FakeVerifier(event, fail=True)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        bad = await client.post(
            "/webhooks/stripe",
            content=b"{}",
            headers={"Stripe-Signature": "sig"},
        )

    assert bad.status_code == 400
