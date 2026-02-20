"""Unit tests for Redis idempotency store."""

from __future__ import annotations

import asyncio

import fakeredis.aioredis
import pytest

from app.services.idempotency import IdempotencyStore


@pytest.fixture
async def idempotency_store() -> IdempotencyStore:
    """Create Redis-backed idempotency store using fakeredis."""

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    store = IdempotencyStore(redis_client=redis, ttl_seconds=1)
    yield store
    await redis.aclose()


@pytest.mark.asyncio
async def test_is_duplicate_first_then_second_call(idempotency_store: IdempotencyStore) -> None:
    """First check passes, second is duplicate."""

    assert await idempotency_store.is_duplicate("evt_123") is False
    assert await idempotency_store.is_duplicate("evt_123") is True


@pytest.mark.asyncio
async def test_expired_ttl_allows_event_again(idempotency_store: IdempotencyStore) -> None:
    """After TTL expiry an event should be processed again."""

    assert await idempotency_store.is_duplicate("evt_expire") is False
    await asyncio.sleep(1.1)
    assert await idempotency_store.is_duplicate("evt_expire") is False


@pytest.mark.asyncio
async def test_concurrent_calls_allow_exactly_one(idempotency_store: IdempotencyStore) -> None:
    """Concurrent duplicate checks should allow only one non-duplicate."""

    results = await asyncio.gather(
        *(idempotency_store.is_duplicate("evt_concurrent") for _ in range(10))
    )
    assert results.count(False) == 1
    assert results.count(True) == 9
