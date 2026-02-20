"""Unit tests for async processor pipeline."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.services.async_processor import AsyncProcessor
from app.services.event_router import EventRouter


class _FakeIdempotencyStore:
    def __init__(self, duplicate: bool = False) -> None:
        self.duplicate = duplicate
        self.marked: list[str] = []
        self.cleared: list[str] = []

    async def is_duplicate(self, event_id: str) -> bool:
        return self.duplicate

    async def mark_processed(self, event_id: str) -> None:
        self.marked.append(event_id)

    async def clear_processing(self, event_id: str) -> None:
        self.cleared.append(event_id)


class _FakePublisher:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[tuple[str, dict[str, Any], str]] = []

    async def publish(self, topic: str, payload: dict[str, Any], event_id: str) -> None:
        self.calls.append((topic, payload, event_id))
        if self.should_fail:
            raise RuntimeError("publish failed")


@pytest.mark.asyncio
async def test_process_one_success(load_fixture) -> None:
    """Processor should route, normalize, publish, and mark processed."""

    idempotency = _FakeIdempotencyStore(duplicate=False)
    publisher = _FakePublisher(should_fail=False)

    processor = AsyncProcessor(
        queue_size=4,
        shutdown_timeout_seconds=2,
        idempotency_store=idempotency,  # type: ignore[arg-type]
        event_router=EventRouter(),
        solace_publisher=publisher,  # type: ignore[arg-type]
    )

    event = load_fixture("payment_intent.succeeded.json")
    await processor._process_one(event)

    assert idempotency.marked == [event["id"]]
    assert len(publisher.calls) == 1
    topic, payload, event_id = publisher.calls[0]
    assert event_id == event["id"]
    assert topic.endswith("/acct_test")
    assert payload["event_type"] == event["type"]


@pytest.mark.asyncio
async def test_process_one_duplicate_skips_publish(load_fixture) -> None:
    """Duplicate events should be skipped before publish."""

    idempotency = _FakeIdempotencyStore(duplicate=True)
    publisher = _FakePublisher(should_fail=False)

    processor = AsyncProcessor(
        queue_size=4,
        shutdown_timeout_seconds=2,
        idempotency_store=idempotency,  # type: ignore[arg-type]
        event_router=EventRouter(),
        solace_publisher=publisher,  # type: ignore[arg-type]
    )

    event = load_fixture("payment_intent.succeeded.json")
    await processor._process_one(event)

    assert publisher.calls == []
    assert idempotency.marked == []


@pytest.mark.asyncio
async def test_process_failure_clears_processing_lock(load_fixture) -> None:
    """Publish failures should clear processing lock for retry."""

    idempotency = _FakeIdempotencyStore(duplicate=False)
    publisher = _FakePublisher(should_fail=True)

    processor = AsyncProcessor(
        queue_size=4,
        shutdown_timeout_seconds=2,
        idempotency_store=idempotency,  # type: ignore[arg-type]
        event_router=EventRouter(),
        solace_publisher=publisher,  # type: ignore[arg-type]
    )

    event = load_fixture("payment_intent.succeeded.json")
    await processor._process_one(event)

    assert idempotency.cleared == [event["id"]]


@pytest.mark.asyncio
async def test_enqueue_returns_false_when_queue_full(load_fixture) -> None:
    """Enqueue should return False when queue is full."""

    processor = AsyncProcessor(
        queue_size=1,
        shutdown_timeout_seconds=1,
        idempotency_store=_FakeIdempotencyStore(),  # type: ignore[arg-type]
        event_router=EventRouter(),
        solace_publisher=_FakePublisher(),  # type: ignore[arg-type]
    )

    event = load_fixture("payment_intent.succeeded.json")
    assert processor.enqueue(event)
    assert not processor.enqueue(event)


@pytest.mark.asyncio
async def test_start_stop_drains_queue(load_fixture) -> None:
    """Worker should process queued events and stop gracefully."""

    idempotency = _FakeIdempotencyStore(duplicate=False)
    publisher = _FakePublisher(should_fail=False)
    processor = AsyncProcessor(
        queue_size=4,
        shutdown_timeout_seconds=2,
        idempotency_store=idempotency,  # type: ignore[arg-type]
        event_router=EventRouter(),
        solace_publisher=publisher,  # type: ignore[arg-type]
    )

    event = load_fixture("customer.created.json")
    await processor.start()
    assert processor.enqueue(event)
    await asyncio.sleep(0.2)
    await processor.stop()

    assert len(publisher.calls) == 1
    assert idempotency.marked == [event["id"]]
