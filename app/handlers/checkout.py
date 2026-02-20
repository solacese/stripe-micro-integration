"""Checkout session event handler."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.handlers.base import BaseEventHandler


class CheckoutSessionHandler(BaseEventHandler):
    """Normalize checkout.session.* events."""

    def extract_data(self, event: Mapping[str, Any]) -> dict[str, Any]:
        obj = (event.get("data", {}) or {}).get("object", {})
        if not isinstance(obj, Mapping):
            return {}

        line_items = obj.get("line_items", {})
        lines = line_items.get("data", []) if isinstance(line_items, Mapping) else []

        return {
            "id": obj.get("id"),
            "customer": obj.get("customer"),
            "mode": obj.get("mode"),
            "payment_status": obj.get("payment_status"),
            "amount_total": obj.get("amount_total"),
            "metadata": obj.get("metadata", {}),
            "line_items_summary": [
                {
                    "description": line.get("description") if isinstance(line, Mapping) else None,
                    "quantity": line.get("quantity") if isinstance(line, Mapping) else None,
                    "amount_total": line.get("amount_total") if isinstance(line, Mapping) else None,
                }
                for line in lines
            ],
        }
