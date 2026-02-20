"""Payout event handler."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.handlers.base import BaseEventHandler


class PayoutHandler(BaseEventHandler):
    """Normalize payout.* events."""

    def extract_data(self, event: Mapping[str, Any]) -> dict[str, Any]:
        obj = (event.get("data", {}) or {}).get("object", {})
        if not isinstance(obj, Mapping):
            return {}

        return {
            "id": obj.get("id"),
            "amount": obj.get("amount"),
            "currency": obj.get("currency"),
            "status": obj.get("status"),
            "arrival_date": obj.get("arrival_date"),
            "failure_message": obj.get("failure_message"),
        }
