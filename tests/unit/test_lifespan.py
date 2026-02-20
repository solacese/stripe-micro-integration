"""Unit tests for application lifespan wiring."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI

from app.lifespan import app_lifespan


class _FakeRedis:
    def __init__(self) -> None:
        self.ping_called = False
        self.closed = False

    async def ping(self) -> None:
        self.ping_called = True

    async def aclose(self) -> None:
        self.closed = True


class _FakePublisher:
    def __init__(self) -> None:
        self.connected = False

    @property
    def is_connected(self) -> bool:
        return self.connected

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False


class _FakeProcessor:
    def __init__(self, **kwargs: Any) -> None:
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


@pytest.mark.asyncio
async def test_lifespan_initializes_and_tears_down_dependencies(make_settings, monkeypatch) -> None:
    """Lifespan should wire dependencies into app.state and clean up on exit."""

    app = FastAPI()
    app.state.settings = make_settings()

    fake_redis = _FakeRedis()
    fake_publisher = _FakePublisher()

    monkeypatch.setattr("app.lifespan.Redis.from_url", lambda *args, **kwargs: fake_redis)
    monkeypatch.setattr(
        "app.lifespan.SolacePublisher.get_instance",
        lambda settings: fake_publisher,
    )
    monkeypatch.setattr("app.lifespan.AsyncProcessor", _FakeProcessor)

    async with app_lifespan(app):
        assert app.state.redis_client is fake_redis
        assert app.state.solace_publisher is fake_publisher
        assert app.state.async_processor.started
        assert app.state.started_at > 0

    assert fake_redis.closed
    assert not fake_publisher.is_connected
    assert app.state.async_processor.stopped
