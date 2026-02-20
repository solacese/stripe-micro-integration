"""Invoice event handler."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.handlers.base import BaseEventHandler


class InvoiceHandler(BaseEventHandler):
    """Normalize invoice.* events."""

    def extract_data(self, event: Mapping[str, Any]) -> dict[str, Any]:
        obj = (event.get("data", {}) or {}).get("object", {})
        if not isinstance(obj, Mapping):
            return {}

        lines_obj = obj.get("lines", {})
        lines = lines_obj.get("data", []) if isinstance(lines_obj, Mapping) else []
        return {
            "id": obj.get("id"),
            "customer": obj.get("customer"),
            "subscription": obj.get("subscription"),
            "amount_due": obj.get("amount_due"),
            "amount_paid": obj.get("amount_paid"),
            "status": obj.get("status"),
            "lines_summary": [
                {
                    "id": line.get("id") if isinstance(line, Mapping) else None,
                    "amount": line.get("amount") if isinstance(line, Mapping) else None,
                    "description": line.get("description") if isinstance(line, Mapping) else None,
                }
                for line in lines
            ],
            "attempt_count": obj.get("attempt_count"),
        }
