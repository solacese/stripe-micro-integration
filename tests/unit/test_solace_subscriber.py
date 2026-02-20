"""Unit tests for SolaceSubscriber."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.solace_subscriber import SolaceSubscriber, _decode_payload


class _FakeInboundMessage:
    def __init__(self, payload: str, *, event_id: str = "evt_1") -> None:
        self._payload = payload
        self._event_id = event_id

    def get_payload_as_string(self) -> str:
        return self._payload

    def get_destination_name(self) -> str:
        return "stripe/test"

    def get_correlation_id(self) -> str:
        return self._event_id

    def get_application_message_id(self) -> str:
        return self._event_id

    def get_properties(self) -> dict[str, Any]:
        return {"stripe_account_id": "acct_test"}


class _FakeReceiver:
    def __init__(self, messages: list[_FakeInboundMessage], ack_counter: dict[str, int]) -> None:
        self._messages = messages
        self._ack_counter = ack_counter

    def start(self) -> None:
        return None

    def receive_message(self, timeout: int | None = None) -> _FakeInboundMessage | None:
        if not self._messages:
            return None
        return self._messages.pop(0)

    def ack(self, message: _FakeInboundMessage) -> None:
        self._ack_counter["count"] += 1

    def terminate(self) -> None:
        return None


class _FakeReceiverBuilder:
    def __init__(
        self,
        queue_messages: dict[str, list[_FakeInboundMessage]],
        ack_counter: dict[str, int],
    ) -> None:
        self._queue_messages = queue_messages
        self._ack_counter = ack_counter

    def with_message_client_acknowledgement(self) -> _FakeReceiverBuilder:
        return self

    def with_missing_resources_creation_strategy(self, strategy: Any) -> _FakeReceiverBuilder:
        return self

    def build(self, queue: Any) -> _FakeReceiver:
        name = queue.get_name()
        messages = self._queue_messages.setdefault(name, [])
        return _FakeReceiver(messages, self._ack_counter)


class _FakeMessagingService:
    def __init__(
        self,
        queue_messages: dict[str, list[_FakeInboundMessage]],
        ack_counter: dict[str, int],
    ) -> None:
        self._queue_messages = queue_messages
        self._ack_counter = ack_counter
        self.is_connected = False

    def connect(self) -> None:
        self.is_connected = True

    def disconnect(self) -> None:
        self.is_connected = False

    def create_persistent_message_receiver_builder(self) -> _FakeReceiverBuilder:
        return _FakeReceiverBuilder(self._queue_messages, self._ack_counter)


@pytest.mark.asyncio
async def test_consume_one_ack_and_meta(make_settings, monkeypatch) -> None:
    """consume_one should decode payload, include metadata, and ACK when requested."""

    queue_messages = {
        "queue.1": [_FakeInboundMessage('{"event_id": "evt_1", "value": 10}', event_id="evt_1")]
    }
    ack_counter = {"count": 0}
    fake_service = _FakeMessagingService(queue_messages, ack_counter)

    subscriber = SolaceSubscriber(make_settings())
    monkeypatch.setattr(subscriber, "_build_service", lambda: fake_service)

    message = await subscriber.consume_one("queue.1", include_meta=True)

    assert message is not None
    assert message["event_id"] == "evt_1"
    assert message["_solace_meta"]["correlation_id"] == "evt_1"
    assert ack_counter["count"] == 1


@pytest.mark.asyncio
async def test_consume_n_and_drain_queue(make_settings, monkeypatch) -> None:
    """consume_n reads multiple messages and drain_queue clears remaining items."""

    queue_messages = {
        "queue.2": [
            _FakeInboundMessage('{"n": 1}', event_id="evt_1"),
            _FakeInboundMessage('{"n": 2}', event_id="evt_2"),
            _FakeInboundMessage('{"n": 3}', event_id="evt_3"),
        ]
    }
    ack_counter = {"count": 0}
    fake_service = _FakeMessagingService(queue_messages, ack_counter)

    subscriber = SolaceSubscriber(make_settings())
    monkeypatch.setattr(subscriber, "_build_service", lambda: fake_service)

    messages = await subscriber.consume_n("queue.2", n=2, timeout_seconds=1)
    assert [msg["n"] for msg in messages] == [1, 2]

    drained = await subscriber.drain_queue("queue.2")
    assert drained == 1


@pytest.mark.asyncio
async def test_connect_disconnect(make_settings, monkeypatch) -> None:
    """connect/disconnect should toggle messaging service connection state."""

    queue_messages: dict[str, list[_FakeInboundMessage]] = {}
    ack_counter = {"count": 0}
    fake_service = _FakeMessagingService(queue_messages, ack_counter)

    subscriber = SolaceSubscriber(make_settings())
    monkeypatch.setattr(subscriber, "_build_service", lambda: fake_service)

    await subscriber.connect()
    assert fake_service.is_connected

    await subscriber.disconnect()
    assert not fake_service.is_connected


def test_decode_payload_handles_json_and_plain_text() -> None:
    """Payload decoding should support JSON and fallback raw payload mode."""

    assert _decode_payload('{"x": 1}') == {"x": 1}
    assert _decode_payload("not-json") == {"raw_payload": "not-json"}
    assert _decode_payload(None) == {}
