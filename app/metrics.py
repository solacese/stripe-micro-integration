"""Prometheus metrics definitions and helpers."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

stripe_webhooks_received_total = Counter(
    "stripe_webhooks_received_total",
    "Total Stripe webhooks received.",
    labelnames=("event_type",),
)
stripe_webhooks_verified_total = Counter(
    "stripe_webhooks_verified_total",
    "Total Stripe webhooks with valid signatures.",
)
stripe_webhooks_invalid_signature_total = Counter(
    "stripe_webhooks_invalid_signature_total",
    "Total Stripe webhook signature verification failures.",
)
stripe_events_processed_total = Counter(
    "stripe_events_processed_total",
    "Total Stripe events processed by status.",
    labelnames=("event_type", "status"),
)
solace_publish_attempts_total = Counter(
    "solace_publish_attempts_total",
    "Total publish attempts to Solace.",
    labelnames=("topic", "status"),
)
solace_publish_failures_total = Counter(
    "solace_publish_failures_total",
    "Total publish failures to Solace after retries.",
    labelnames=("topic",),
)
solace_connection_status = Gauge(
    "solace_connection_status",
    "Solace connection status: 1=connected, 0=disconnected.",
)
async_queue_size = Gauge(
    "async_queue_size",
    "Current async processor queue depth.",
)
event_processing_duration_seconds = Histogram(
    "event_processing_duration_seconds",
    "Duration of event processing pipeline.",
    labelnames=("event_type",),
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration.",
    labelnames=("method", "path", "status_code"),
)


def render_metrics() -> Response:
    """Render metrics in Prometheus text format."""

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
