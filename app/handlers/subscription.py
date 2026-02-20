"""Subscription event handler."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.handlers.base import BaseEventHandler


class SubscriptionHandler(BaseEventHandler):
    """Normalize customer.subscription.* events."""

    def extract_data(self, event: Mapping[str, Any]) -> dict[str, Any]:
        obj = (event.get("data", {}) or {}).get("object", {})
        if not isinstance(obj, Mapping):
            return {}

        plan = obj.get("plan")
        items_obj = obj.get("items", {})
        items_data = items_obj.get("data", []) if isinstance(items_obj, Mapping) else []
        return {
            "id": obj.get("id"),
            "customer": obj.get("customer"),
            "status": obj.get("status"),
            "current_period_start": obj.get("current_period_start"),
            "current_period_end": obj.get("current_period_end"),
            "plan": plan,
            "cancel_at_period_end": obj.get("cancel_at_period_end"),
            "trial_end": obj.get("trial_end"),
            "items": items_data,
        }
