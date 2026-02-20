"""Stripe event type to Solace topic routing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventRouter:
    """Route Stripe event types to topic taxonomy."""

    topic_prefix: str = "stripe/webhook/v1"

    def get_topic(self, event_type: str, account_id: str) -> str:
        """Return destination topic for an event type/account."""

        account_segment = account_id or "unknown"
        mapped_segment = self._map_event_type(event_type)
        return f"{self.topic_prefix}/{mapped_segment}/{account_segment}"

    @staticmethod
    def _map_event_type(event_type: str) -> str:
        mapping = {
            "payment_intent.succeeded": "payment_intent/succeeded",
            "payment_intent.payment_failed": "payment_intent/payment_failed",
            "customer.subscription.created": "subscription/created",
            "customer.subscription.updated": "subscription/updated",
            "customer.subscription.deleted": "subscription/deleted",
            "invoice.payment_succeeded": "invoice/payment_succeeded",
            "invoice.payment_failed": "invoice/payment_failed",
            "invoice.finalized": "invoice/finalized",
            "charge.succeeded": "charge/succeeded",
            "charge.failed": "charge/failed",
            "charge.dispute.created": "charge/dispute/created",
            "customer.created": "customer/created",
            "customer.deleted": "customer/deleted",
            "checkout.session.completed": "checkout/session/completed",
            "payout.failed": "payout/failed",
        }
        return mapping.get(event_type, "error/unroutable")
