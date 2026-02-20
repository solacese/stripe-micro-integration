"""Dispute event handler."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.handlers.base import BaseEventHandler


class DisputeHandler(BaseEventHandler):
    """Normalize charge.dispute.* events."""

    def extract_data(self, event: Mapping[str, Any]) -> dict[str, Any]:
        obj = (event.get("data", {}) or {}).get("object", {})
        if not isinstance(obj, Mapping):
            return {}

        return {
            "id": obj.get("id"),
            "charge": obj.get("charge"),
            "amount": obj.get("amount"),
            "reason": obj.get("reason"),
            "status": obj.get("status"),
            "evidence_due_by": obj.get("evidence_details", {}).get("due_by")
            if isinstance(obj.get("evidence_details"), Mapping)
            else None,
        }
