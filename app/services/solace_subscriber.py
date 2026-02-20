"""Solace durable queue subscriber utilities."""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

from solace.messaging.config.missing_resources_creation_configuration import (
    MissingResourcesCreationStrategy,
)
from solace.messaging.config.retry_strategy import RetryStrategy
from solace.messaging.config.solace_properties import (
    authentication_properties,
    service_properties,
    transport_layer_properties,
)
from solace.messaging.config.transport_security_strategy import TLS
from solace.messaging.messaging_service import MessagingService
from solace.messaging.resources.queue import Queue

from app.config import Settings


class SolaceSubscriber:
    """Consume persistent messages from Solace durable queues."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._messaging_service: MessagingService | None = None

    async def connect(self) -> None:
        """Connect the subscriber to Solace."""

        if self._messaging_service is not None and self._messaging_service.is_connected:
            return

        service = await asyncio.to_thread(self._build_service)
        await asyncio.to_thread(service.connect)
        self._messaging_service = service

    async def disconnect(self) -> None:
        """Disconnect subscriber from Solace."""

        if self._messaging_service is not None:
            await asyncio.to_thread(self._messaging_service.disconnect)
        self._messaging_service = None

    async def consume_one(
        self,
        queue_name: str,
        timeout_seconds: float = 10.0,
        *,
        ack: bool = True,
        include_meta: bool = False,
    ) -> dict[str, Any] | None:
        """Consume and optionally ACK one message from a durable queue."""

        await self.connect()
        if self._messaging_service is None:
            raise RuntimeError("Solace subscriber not connected")

        queue = Queue.durable_non_exclusive_queue(queue_name)
        receiver = (
            self._messaging_service.create_persistent_message_receiver_builder()
            .with_message_client_acknowledgement()
            .with_missing_resources_creation_strategy(MissingResourcesCreationStrategy.DO_NOT_CREATE)
            .build(queue)
        )

        try:
            await asyncio.to_thread(receiver.start)
            inbound = await asyncio.to_thread(receiver.receive_message, int(timeout_seconds * 1000))
            if inbound is None:
                return None

            raw_payload = inbound.get_payload_as_string()
            if raw_payload is not None:
                payload = _decode_payload(raw_payload)
            else:
                raw_bytes = inbound.get_payload_as_bytes()
                if raw_bytes is None:
                    payload = {}
                else:
                    try:
                        payload = _decode_payload(bytes(raw_bytes).decode("utf-8"))
                    except UnicodeDecodeError:
                        payload = {
                            "raw_bytes_base64": base64.b64encode(bytes(raw_bytes)).decode("ascii")
                        }
            if include_meta:
                payload["_solace_meta"] = {
                    "destination": inbound.get_destination_name(),
                    "correlation_id": inbound.get_correlation_id(),
                    "application_message_id": inbound.get_application_message_id(),
                    "properties": inbound.get_properties(),
                }

            if ack:
                await asyncio.to_thread(receiver.ack, inbound)

            return payload
        finally:
            await asyncio.to_thread(receiver.terminate)

    async def consume_n(
        self,
        queue_name: str,
        n: int,
        timeout_seconds: float = 15.0,
        *,
        ack: bool = True,
        include_meta: bool = False,
    ) -> list[dict[str, Any]]:
        """Consume up to n messages before timeout expires."""

        messages: list[dict[str, Any]] = []
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while len(messages) < n:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            msg = await self.consume_one(
                queue_name,
                timeout_seconds=remaining,
                ack=ack,
                include_meta=include_meta,
            )
            if msg is None:
                break
            messages.append(msg)
        return messages

    async def drain_queue(self, queue_name: str) -> int:
        """Drain and ACK all currently available messages from queue."""

        drained = 0
        while True:
            msg = await self.consume_one(queue_name=queue_name, timeout_seconds=0.2)
            if msg is None:
                return drained
            drained += 1

    def _build_service(self) -> MessagingService:
        """Build messaging service for subscriber operations."""

        properties: dict[str, Any] = {
            transport_layer_properties.HOST: self._settings.solace_host,
            service_properties.VPN_NAME: self._settings.solace_vpn,
            authentication_properties.SCHEME_BASIC_USER_NAME: self._settings.solace_username,
            authentication_properties.SCHEME_BASIC_PASSWORD: self._settings.solace_password,
        }
        builder = (
            MessagingService.builder()
            .from_properties(properties)
            .with_reconnection_retry_strategy(RetryStrategy.parametrized_retry(300, 1000))
        )

        if self._settings.solace_tls_enabled:
            tls = TLS.create()
            if self._settings.solace_tls_ca_cert_path:
                tls = tls.with_certificate_validation(
                    ignore_expiration=False,
                    trust_store_file_path=self._settings.solace_tls_ca_cert_path,
                )
            else:
                tls = tls.without_certificate_validation()
            builder = builder.with_transport_security_strategy(tls)

        return builder.build("stripe-solace-subscriber")


def _decode_payload(raw_payload: str | None) -> dict[str, Any]:
    """Decode JSON payload from inbound message payload text."""

    if raw_payload is None:
        return {}
    try:
        decoded = json.loads(raw_payload)
        if isinstance(decoded, dict):
            return decoded
        return {"payload": decoded}
    except json.JSONDecodeError:
        return {"raw_payload": raw_payload}
