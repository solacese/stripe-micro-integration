"""Unit tests for SolacePublisher."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.config import Settings
from app.services.solace_publisher import SolacePublisher


class _FakeMessageBuilder:
    def __init__(self) -> None:
        self.properties: dict[str, Any] = {}
        self.correlation_id: str | None = None
        self.application_message_id: str | None = None
        self.payload: dict[str, Any] | None = None

    def with_application_message_id(self, value: str) -> _FakeMessageBuilder:
        self.application_message_id = value
        return self

    def with_correlation_id(self, value: str) -> _FakeMessageBuilder:
        self.correlation_id = value
        return self

    def with_property(self, key: str, value: Any) -> _FakeMessageBuilder:
        self.properties[key] = value
        return self

    def build(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.payload = payload
        return {
            "payload": payload,
            "correlation_id": self.correlation_id,
            "application_message_id": self.application_message_id,
            "properties": dict(self.properties),
        }


class _FakeMessagingService:
    def __init__(self) -> None:
        self.builder = _FakeMessageBuilder()
        self.is_connected = True

    def message_builder(self) -> _FakeMessageBuilder:
        return self.builder


class _FakePersistentPublisher:
    def __init__(self) -> None:
        self.started = False
        self.terminated = False
        self.listener: Any = None

    def set_message_publish_receipt_listener(self, listener: Any) -> None:
        self.listener = listener

    def start(self) -> None:
        self.started = True

    def terminate(self) -> None:
        self.terminated = True

    def publish(self, **kwargs: Any) -> None:
        return None


class _FakePersistentPublisherBuilder:
    def __init__(self, publisher: _FakePersistentPublisher) -> None:
        self.publisher = publisher

    def on_back_pressure_wait(self, capacity: int) -> _FakePersistentPublisherBuilder:
        return self

    def build(self) -> _FakePersistentPublisher:
        return self.publisher


class _FakeConnectableMessagingService(_FakeMessagingService):
    def __init__(self) -> None:
        super().__init__()
        self.is_connected = False
        self.publisher = _FakePersistentPublisher()
        self.disconnected = False

    def connect(self) -> None:
        self.is_connected = True

    def disconnect(self) -> None:
        self.is_connected = False
        self.disconnected = True

    def create_persistent_message_publisher_builder(self) -> _FakePersistentPublisherBuilder:
        return _FakePersistentPublisherBuilder(self.publisher)


@pytest.fixture
def settings() -> Settings:
    """Create settings object for publisher tests."""

    return Settings(
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


@pytest.mark.asyncio
async def test_publish_calls_publish_once_on_success(settings: Settings) -> None:
    """Successful publish should invoke underlying publish once."""

    publisher = SolacePublisher(settings)
    publisher._messaging_service = _FakeMessagingService()  # type: ignore[attr-defined]
    publisher._publisher = MagicMock()  # type: ignore[attr-defined]

    payload = {"event_type": "payment_intent.succeeded", "account_id": "acct_xxx"}
    await publisher.publish(
        "stripe/webhook/v1/payment_intent/succeeded/acct_xxx",
        payload,
        "evt_123",
    )

    assert publisher._publisher.publish.call_count == 1  # type: ignore[attr-defined]


def test_publish_blocking_sets_expected_message_properties(settings: Settings) -> None:
    """Blocking publish sets message IDs and DMQ eligibility properties."""

    publisher = SolacePublisher(settings)
    fake_service = _FakeMessagingService()
    fake_pub = MagicMock()

    publisher._messaging_service = fake_service  # type: ignore[attr-defined]
    publisher._publisher = fake_pub  # type: ignore[attr-defined]

    payload = {
        "event_id": "evt_999",
        "event_type": "payment_intent.succeeded",
        "api_version": "2023-10-16",
        "account_id": "acct_xxx",
        "created_at": 1708000000,
        "bridge_received_at": "2026-02-20T00:00:00Z",
    }

    publisher._publish_blocking(
        "stripe/webhook/v1/payment_intent/succeeded/acct_xxx",
        payload,
        "evt_999",
    )

    message = fake_pub.publish.call_args.kwargs["message"]
    assert message["correlation_id"] == "evt_999"
    assert message["application_message_id"] == "evt_999"
    assert any("dmq" in key.lower() for key in message["properties"])


@pytest.mark.asyncio
async def test_publish_retries_and_swallows_errors(settings: Settings, monkeypatch) -> None:
    """Publish errors are retried and not propagated."""

    publisher = SolacePublisher(settings)
    publisher._messaging_service = _FakeMessagingService()  # type: ignore[attr-defined]
    publisher._publisher = MagicMock()  # type: ignore[attr-defined]

    calls = {"count": 0}

    def _raise_once(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        raise RuntimeError("boom")

    monkeypatch.setattr(publisher, "_publish_blocking", _raise_once)

    await publisher.publish("stripe/webhook/v1/error/unroutable/acct_xxx", {"a": 1}, "evt_err")

    assert calls["count"] == settings.max_publish_retries


@pytest.mark.asyncio
async def test_connect_and_disconnect_lifecycle(settings: Settings, monkeypatch) -> None:
    """connect and disconnect should manage service and publisher lifecycle."""

    publisher = SolacePublisher(settings)
    fake_service = _FakeConnectableMessagingService()
    monkeypatch.setattr(publisher, "_build_service", lambda: fake_service)

    await publisher.connect()
    assert publisher.is_connected
    assert fake_service.publisher.started

    await publisher.disconnect()
    assert not publisher.is_connected
    assert fake_service.disconnected
    assert fake_service.publisher.terminated


@pytest.mark.asyncio
async def test_publish_handles_connect_error(settings: Settings, monkeypatch) -> None:
    """publish should swallow connection errors and never raise."""

    publisher = SolacePublisher(settings)

    async def _raise_connect() -> None:
        raise RuntimeError("connect error")

    monkeypatch.setattr(publisher, "connect", _raise_connect)
    await publisher.publish("stripe/webhook/v1/topic/acct_xxx", {"event_id": "evt_1"}, "evt_1")


def test_build_service_covers_tls_branch(make_settings) -> None:
    """_build_service should build with TLS branch enabled."""

    settings = make_settings(SOLACE_TLS_ENABLED=True)
    publisher = SolacePublisher(settings)
    service = publisher._build_service()
    assert service is not None
