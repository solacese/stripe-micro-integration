"""Application lifespan context."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import monotonic

from fastapi import FastAPI
from redis.asyncio import Redis

from app.config import Settings
from app.services.async_processor import AsyncProcessor
from app.services.event_router import EventRouter
from app.services.idempotency import IdempotencyStore
from app.services.solace_publisher import SolacePublisher
from app.services.stripe_verifier import StripeVerifier


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and teardown application dependencies."""

    settings: Settings = app.state.settings

    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    await redis_client.ping()

    idempotency_store = IdempotencyStore(
        redis_client=redis_client,
        ttl_seconds=settings.idempotency_ttl_seconds,
    )
    event_router = EventRouter()
    solace_publisher = SolacePublisher.get_instance(settings)
    await solace_publisher.connect()

    async_processor = AsyncProcessor(
        queue_size=settings.async_queue_size,
        shutdown_timeout_seconds=settings.async_shutdown_timeout_seconds,
        idempotency_store=idempotency_store,
        event_router=event_router,
        solace_publisher=solace_publisher,
    )
    await async_processor.start()

    stripe_verifier = StripeVerifier(settings.stripe_webhook_secret)

    app.state.redis_client = redis_client
    app.state.idempotency_store = idempotency_store
    app.state.event_router = event_router
    app.state.solace_publisher = solace_publisher
    app.state.async_processor = async_processor
    app.state.stripe_verifier = stripe_verifier
    app.state.started_at = monotonic()

    try:
        yield
    finally:
        await async_processor.stop()
        await solace_publisher.disconnect()
        await redis_client.aclose()
