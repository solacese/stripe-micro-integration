"""Base event handler implementation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app import __version__
from app.models.stripe_event import StripeEventEnvelope


class BaseEventHandler:
    """Base class for Stripe event handlers."""

    def extract_data(self, event: Mapping[str, Any]) -> dict[str, Any]:
        """Extract event-specific normalized fields."""

        return {}

    def normalize(
        self,
        event: Mapping[str, Any],
        *,
        bridge_received_at: str,
        trace_id: str,
    ) -> dict[str, Any]:
        """Convert raw Stripe event into normalized envelope dict."""

        event_data = event.get("data", {})
        raw_obj = event_data.get("object", {}) if isinstance(event_data, Mapping) else {}

        envelope = StripeEventEnvelope(
            event_id=str(event.get("id", "")),
            event_type=str(event.get("type", "unknown")),
            api_version=(
                str(event.get("api_version")) if event.get("api_version") is not None else None
            ),
            account_id=str(event.get("account") or "unknown"),
            created_at=int(event.get("created", 0)),
            bridge_received_at=bridge_received_at,
            bridge_version=__version__,
            trace_id=trace_id,
            data=self.extract_data(event),
            raw=raw_obj if isinstance(raw_obj, dict) else {},
        )
        return envelope.model_dump(mode="json")
