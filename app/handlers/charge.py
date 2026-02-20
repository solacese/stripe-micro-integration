"""Charge event handler."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.handlers.base import BaseEventHandler


class ChargeHandler(BaseEventHandler):
    """Normalize charge.* events."""

    def extract_data(self, event: Mapping[str, Any]) -> dict[str, Any]:
        obj = (event.get("data", {}) or {}).get("object", {})
        if not isinstance(obj, Mapping):
            return {}

        outcome = obj.get("outcome") if isinstance(obj.get("outcome"), Mapping) else {}
        return {
            "id": obj.get("id"),
            "amount": obj.get("amount"),
            "currency": obj.get("currency"),
            "status": obj.get("status"),
            "outcome": outcome,
            "risk_level": outcome.get("risk_level") if isinstance(outcome, Mapping) else None,
            "risk_score": outcome.get("risk_score") if isinstance(outcome, Mapping) else None,
        }
