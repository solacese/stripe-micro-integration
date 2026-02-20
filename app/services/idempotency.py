"""Redis-based idempotency service."""

from __future__ import annotations

from redis.asyncio import Redis


class IdempotencyStore:
    """Manage event idempotency state in Redis."""

    def __init__(self, redis_client: Redis, ttl_seconds: int) -> None:
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds

    async def is_duplicate(self, event_id: str) -> bool:
        """Return True when event is currently processing or already processed."""

        processing_key = self._processing_key(event_id)
        processed_key = self._processed_key(event_id)

        if await self._redis.exists(processed_key):
            return True

        acquired = await self._redis.set(processing_key, "1", ex=self._ttl_seconds, nx=True)
        return not bool(acquired)

    async def mark_processed(self, event_id: str) -> None:
        """Mark event as processed and release processing lock."""

        processing_key = self._processing_key(event_id)
        processed_key = self._processed_key(event_id)

        async with self._redis.pipeline(transaction=True) as pipeline:
            await pipeline.set(processed_key, "1", ex=self._ttl_seconds)
            await pipeline.delete(processing_key)
            await pipeline.execute()

    async def clear_processing(self, event_id: str) -> None:
        """Release processing lock for failed processing."""

        await self._redis.delete(self._processing_key(event_id))

    @staticmethod
    def _processing_key(event_id: str) -> str:
        return f"stripe:bridge:processing:{event_id}"

    @staticmethod
    def _processed_key(event_id: str) -> str:
        return f"stripe:bridge:processed:{event_id}"
