"""Solace persistent publisher service."""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

import structlog
from solace.messaging.config.retry_strategy import RetryStrategy
from solace.messaging.config.solace_properties import (
    authentication_properties,
    message_properties,
    service_properties,
    transport_layer_properties,
)
from solace.messaging.config.transport_security_strategy import TLS
from solace.messaging.errors.pubsubplus_client_error import PubSubPlusClientError
from solace.messaging.messaging_service import MessagingService
from solace.messaging.publisher.persistent_message_publisher import (
    MessagePublishReceiptListener,
    PersistentMessagePublisher,
    PublishReceipt,
)
from solace.messaging.resources.topic import Topic

from app.config import Settings
from app.metrics import (
    solace_connection_status,
    solace_publish_attempts_total,
    solace_publish_failures_total,
)


class _ReceiptListener(MessagePublishReceiptListener):  # type: ignore[misc]
    """Log publish acknowledgements from Solace."""

    def __init__(self) -> None:
        self._logger = structlog.get_logger("solace_receipts")

    def on_publish_receipt(self, publish_receipt: PublishReceipt) -> None:
        self._logger.debug("solace_publish_receipt", receipt=repr(publish_receipt))


class SolacePublisher:
    """Publish normalized Stripe events to Solace topics."""

    _instance: SolacePublisher | None = None
    _singleton_lock = threading.Lock()

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = structlog.get_logger("solace_publisher")
        self._messaging_service: MessagingService | None = None
        self._publisher: PersistentMessagePublisher | None = None

    @classmethod
    def get_instance(cls, settings: Settings) -> SolacePublisher:
        """Return a singleton instance for runtime safety."""

        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = cls(settings)
            return cls._instance

    @property
    def is_connected(self) -> bool:
        """Return whether the messaging service is connected."""

        if self._messaging_service is None:
            return False
        return bool(self._messaging_service.is_connected)

    async def connect(self) -> None:
        """Connect to Solace and start persistent publisher."""

        if self.is_connected and self._publisher is not None:
            return

        service = await asyncio.to_thread(self._build_service)
        await asyncio.to_thread(service.connect)
        publisher = service.create_persistent_message_publisher_builder().on_back_pressure_wait(
            self._settings.async_queue_size
        ).build()
        publisher.start()
        publisher.set_message_publish_receipt_listener(_ReceiptListener())

        self._messaging_service = service
        self._publisher = publisher
        solace_connection_status.set(1)
        self._logger.info(
            "solace_connected",
            host=self._settings.solace_host,
            vpn=self._settings.solace_vpn,
        )

    async def disconnect(self) -> None:
        """Terminate publisher and disconnect from Solace."""

        if self._publisher is not None:
            await asyncio.to_thread(self._publisher.terminate)
        if self._messaging_service is not None:
            await asyncio.to_thread(self._messaging_service.disconnect)

        self._publisher = None
        self._messaging_service = None
        solace_connection_status.set(0)
        self._logger.info("solace_disconnected")

    async def publish(self, topic: str, payload: dict[str, Any], event_id: str) -> None:
        """Publish payload with retry and never raise to caller."""

        if self._publisher is None or self._messaging_service is None:
            try:
                await self.connect()
            except Exception as exc:
                solace_publish_attempts_total.labels(topic=topic, status="error").inc()
                solace_publish_failures_total.labels(topic=topic).inc()
                self._logger.error("solace_connect_failed", error=str(exc), topic=topic)
                return

        if self._publisher is None or self._messaging_service is None:
            solace_publish_attempts_total.labels(topic=topic, status="error").inc()
            solace_publish_failures_total.labels(topic=topic).inc()
            return

        attempts = max(1, self._settings.max_publish_retries)

        for attempt in range(1, attempts + 1):
            try:
                await asyncio.to_thread(self._publish_blocking, topic, payload, event_id)
                solace_publish_attempts_total.labels(topic=topic, status="success").inc()
                return
            except PubSubPlusClientError as exc:
                await self._handle_publish_exception(
                    topic=topic,
                    attempt=attempt,
                    attempts=attempts,
                    error=exc,
                )
            except Exception as exc:
                await self._handle_publish_exception(
                    topic=topic,
                    attempt=attempt,
                    attempts=attempts,
                    error=exc,
                )

    async def _handle_publish_exception(
        self,
        *,
        topic: str,
        attempt: int,
        attempts: int,
        error: Exception,
    ) -> None:
        """Handle publish failures with retry and metrics updates."""

        if attempt >= attempts:
            solace_publish_attempts_total.labels(topic=topic, status="failure").inc()
            solace_publish_failures_total.labels(topic=topic).inc()
            self._logger.error(
                "solace_publish_failed",
                topic=topic,
                attempt=attempt,
                max_attempts=attempts,
                error=str(error),
            )
            return

        solace_publish_attempts_total.labels(topic=topic, status="retry").inc()
        delay = self._settings.retry_backoff_base_seconds * (2 ** (attempt - 1))
        self._logger.warning(
            "solace_publish_retry",
            topic=topic,
            attempt=attempt,
            max_attempts=attempts,
            delay_seconds=delay,
            error=str(error),
        )
        await asyncio.sleep(delay)

    def _publish_blocking(self, topic: str, payload: dict[str, Any], event_id: str) -> None:
        """Publish message through sync Solace APIs."""

        if self._messaging_service is None or self._publisher is None:
            raise RuntimeError("Solace publisher is not initialized")

        message_builder = self._messaging_service.message_builder()
        serialized_payload = json.dumps(payload, separators=(",", ":"), default=str)
        message = (
            message_builder.with_application_message_id(event_id)
            .with_correlation_id(event_id)
            .with_property(message_properties.HTTP_CONTENT_TYPE, "application/json")
            .with_property(message_properties.PERSISTENT_DMQ_ELIGIBLE, self._settings.dmq_eligible)
            .with_property(
                message_properties.PERSISTENT_TIME_TO_LIVE,
                self._settings.solace_message_ttl_ms,
            )
            .with_property("stripe_api_version", payload.get("api_version"))
            .with_property("stripe_account_id", payload.get("account_id"))
            .with_property("event_created_at", payload.get("created_at"))
            .with_property("bridge_received_at", payload.get("bridge_received_at"))
            .build(serialized_payload)
        )

        self._publisher.publish(
            message=message,
            destination=Topic.of(topic),
            user_context={"event_id": event_id, "topic": topic},
        )

    def _build_service(self) -> MessagingService:
        """Build a configured messaging service instance."""

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

        return builder.build("stripe-solace-bridge")
