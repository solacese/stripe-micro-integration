"""Async background event processing pipeline."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

import structlog

from app.handlers.base import BaseEventHandler
from app.handlers.charge import ChargeHandler
from app.handlers.checkout import CheckoutSessionHandler
from app.handlers.customer import CustomerHandler
from app.handlers.dispute import DisputeHandler
from app.handlers.invoice import InvoiceHandler
from app.handlers.payment_intent import PaymentIntentHandler
from app.handlers.payout import PayoutHandler
from app.handlers.subscription import SubscriptionHandler
from app.metrics import (
    async_queue_size,
    event_processing_duration_seconds,
    stripe_events_processed_total,
)
from app.services.event_router import EventRouter
from app.services.idempotency import IdempotencyStore
from app.services.solace_publisher import SolacePublisher


class AsyncProcessor:
    """Queue-backed background processor for Stripe events."""

    def __init__(
        self,
        *,
        queue_size: int,
        shutdown_timeout_seconds: int,
        idempotency_store: IdempotencyStore,
        event_router: EventRouter,
        solace_publisher: SolacePublisher,
    ) -> None:
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=queue_size)
        self._shutdown_timeout_seconds = shutdown_timeout_seconds
        self._idempotency_store = idempotency_store
        self._event_router = event_router
        self._solace_publisher = solace_publisher
        self._worker_task: asyncio.Task[None] | None = None
        self._logger = structlog.get_logger("async_processor")
        self._stop_event = asyncio.Event()

        self._handler_map: dict[str, BaseEventHandler] = {
            "payment_intent.": PaymentIntentHandler(),
            "customer.subscription.": SubscriptionHandler(),
            "invoice.": InvoiceHandler(),
            "charge.dispute.": DisputeHandler(),
            "charge.": ChargeHandler(),
            "customer.": CustomerHandler(),
            "checkout.session.": CheckoutSessionHandler(),
            "payout.": PayoutHandler(),
        }

    async def start(self) -> None:
        """Start background worker."""

        if self._worker_task is not None and not self._worker_task.done():
            return
        self._stop_event.clear()
        self._worker_task = asyncio.create_task(self._run(), name="async-event-processor")

    async def stop(self) -> None:
        """Signal worker to stop and drain queued events."""

        self._stop_event.set()
        if self._worker_task is None:
            return

        try:
            await asyncio.wait_for(self._worker_task, timeout=self._shutdown_timeout_seconds)
        except TimeoutError:
            self._logger.warning("processor_shutdown_timeout", queue_size=self._queue.qsize())
            self._worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._worker_task

    def enqueue(self, event: Mapping[str, Any]) -> bool:
        """Try enqueueing an event; return False when queue is full."""

        try:
            self._queue.put_nowait(dict(event))
            async_queue_size.set(self._queue.qsize())
            return True
        except asyncio.QueueFull:
            return False

    async def _run(self) -> None:
        """Process queued events until drained during shutdown."""

        while True:
            if self._stop_event.is_set() and self._queue.empty():
                return

            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=0.25)
            except TimeoutError:
                continue

            async_queue_size.set(self._queue.qsize())
            try:
                await self._process_one(event)
            finally:
                self._queue.task_done()
                async_queue_size.set(self._queue.qsize())

    async def _process_one(self, event: Mapping[str, Any]) -> None:
        """Run the full event processing chain for one event."""

        event_id = str(event.get("id", ""))
        event_type = str(event.get("type", "unknown"))
        account_id = str(event.get("account") or "unknown")
        start = perf_counter()

        try:
            if not event_id:
                stripe_events_processed_total.labels(event_type=event_type, status="invalid").inc()
                self._logger.warning("event_missing_id", event_type=event_type)
                return

            if await self._idempotency_store.is_duplicate(event_id):
                stripe_events_processed_total.labels(
                    event_type=event_type,
                    status="duplicate",
                ).inc()
                self._logger.info(
                    "duplicate_event_skipped",
                    event_id=event_id,
                    event_type=event_type,
                )
                return

            topic = self._event_router.get_topic(event_type, account_id)
            bridge_received_at = datetime.now(UTC).isoformat()
            trace_id = str(uuid4())

            handler = self._resolve_handler(event_type)
            normalized_payload = handler.normalize(
                event,
                bridge_received_at=bridge_received_at,
                trace_id=trace_id,
            )

            await self._solace_publisher.publish(topic, normalized_payload, event_id)
            await self._idempotency_store.mark_processed(event_id)
            stripe_events_processed_total.labels(event_type=event_type, status="success").inc()
        except Exception as exc:
            stripe_events_processed_total.labels(event_type=event_type, status="failure").inc()
            if event_id:
                await self._idempotency_store.clear_processing(event_id)
            self._logger.error(
                "event_processing_failed",
                event_id=event_id,
                event_type=event_type,
                error=str(exc),
            )
        finally:
            elapsed = max(0.0, perf_counter() - start)
            event_processing_duration_seconds.labels(event_type=event_type).observe(elapsed)

    def _resolve_handler(self, event_type: str) -> BaseEventHandler:
        """Return best matching handler for event type."""

        for prefix, handler in self._handler_map.items():
            if event_type.startswith(prefix):
                return handler
        return BaseEventHandler()
