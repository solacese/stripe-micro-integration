"""Payment intent event handler."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.handlers.base import BaseEventHandler


class PaymentIntentHandler(BaseEventHandler):
    """Normalize payment intent events."""

    def extract_data(self, event: Mapping[str, Any]) -> dict[str, Any]:
        obj = (event.get("data", {}) or {}).get("object", {})
        if not isinstance(obj, Mapping):
            return {}
        return {
            "id": obj.get("id"),
            "amount": obj.get("amount"),
            "currency": obj.get("currency"),
            "status": obj.get("status"),
            "customer": obj.get("customer"),
            "payment_method": obj.get("payment_method"),
            "metadata": obj.get("metadata", {}),
            "last_payment_error": obj.get("last_payment_error"),
        }
