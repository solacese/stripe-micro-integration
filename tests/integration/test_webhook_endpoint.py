"""Integration tests for webhook HTTP endpoint."""

from __future__ import annotations

import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from app.services.stripe_verifier import WebhookVerificationError


class _FakeVerifier:
    def __init__(self, event):  # type: ignore[no-untyped-def]
        self.event = event

    def verify(self, payload: bytes, signature_header: str | None):  # type: ignore[no-untyped-def]
        if signature_header == "bad":
            raise WebhookVerificationError("invalid")
        return self.event


class _FakeProcessor:
    def __init__(self, enqueue_result: bool = True) -> None:
        self.enqueue_result = enqueue_result
        self.events: list[dict] = []

    def enqueue(self, event):  # type: ignore[no-untyped-def]
        self.events.append(event)
        return self.enqueue_result


@pytest.mark.asyncio
async def test_webhook_returns_200_and_enqueues_event(load_fixture) -> None:
    """Webhook endpoint returns quickly and enqueues event on valid signature."""

    settings = Settings(
        STRIPE_WEBHOOK_SECRET="whsec_test",
        STRIPE_API_KEY="",
        SOLACE_HOST="tcp://localhost:55555",
        SOLACE_SEMP_HOST="http://localhost:8080",
        SOLACE_SEMP_USERNAME="admin",
        SOLACE_SEMP_PASSWORD="admin",
        SOLACE_VPN="default",
        SOLACE_USERNAME="user",
        SOLACE_PASSWORD="pass",
        SOLACE_TLS_ENABLED=False,
        SOLACE_TLS_CA_CERT_PATH="",
        REDIS_URL="redis://localhost:6379/0",
    )
    app = create_app(settings)

    event = load_fixture("payment_intent.succeeded.json")
    processor = _FakeProcessor(enqueue_result=True)
    app.state.stripe_verifier = _FakeVerifier(event)
    app.state.async_processor = processor

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        start = time.perf_counter()
        response = await client.post(
            "/webhooks/stripe",
            content=b"{}",
            headers={"Stripe-Signature": "valid"},
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

    assert response.status_code == 200
    assert elapsed_ms < 300
    assert len(processor.events) == 1


@pytest.mark.asyncio
async def test_webhook_returns_400_on_invalid_signature(load_fixture) -> None:
    """Webhook endpoint returns 400 on signature verification errors."""

    settings = Settings(
        STRIPE_WEBHOOK_SECRET="whsec_test",
        STRIPE_API_KEY="",
        SOLACE_HOST="tcp://localhost:55555",
        SOLACE_SEMP_HOST="http://localhost:8080",
        SOLACE_SEMP_USERNAME="admin",
        SOLACE_SEMP_PASSWORD="admin",
        SOLACE_VPN="default",
        SOLACE_USERNAME="user",
        SOLACE_PASSWORD="pass",
        SOLACE_TLS_ENABLED=False,
        SOLACE_TLS_CA_CERT_PATH="",
        REDIS_URL="redis://localhost:6379/0",
    )
    app = create_app(settings)

    event = load_fixture("payment_intent.succeeded.json")
    app.state.stripe_verifier = _FakeVerifier(event)
    app.state.async_processor = _FakeProcessor(enqueue_result=True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/webhooks/stripe",
            content=b"{}",
            headers={"Stripe-Signature": "bad"},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_webhook_returns_429_when_queue_full(load_fixture) -> None:
    """Webhook endpoint returns 429 when async queue is full."""

    settings = Settings(
        STRIPE_WEBHOOK_SECRET="whsec_test",
        STRIPE_API_KEY="",
        SOLACE_HOST="tcp://localhost:55555",
        SOLACE_SEMP_HOST="http://localhost:8080",
        SOLACE_SEMP_USERNAME="admin",
        SOLACE_SEMP_PASSWORD="admin",
        SOLACE_VPN="default",
        SOLACE_USERNAME="user",
        SOLACE_PASSWORD="pass",
        SOLACE_TLS_ENABLED=False,
        SOLACE_TLS_CA_CERT_PATH="",
        REDIS_URL="redis://localhost:6379/0",
    )
    app = create_app(settings)

    event = load_fixture("payment_intent.succeeded.json")
    app.state.stripe_verifier = _FakeVerifier(event)
    app.state.async_processor = _FakeProcessor(enqueue_result=False)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/webhooks/stripe",
            content=b"{}",
            headers={"Stripe-Signature": "valid"},
        )

    assert response.status_code == 429
