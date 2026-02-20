"""Customer event handler."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.handlers.base import BaseEventHandler


class CustomerHandler(BaseEventHandler):
    """Normalize customer.* events."""

    def extract_data(self, event: Mapping[str, Any]) -> dict[str, Any]:
        obj = (event.get("data", {}) or {}).get("object", {})
        if not isinstance(obj, Mapping):
            return {}

        return {
            "id": obj.get("id"),
            "email": obj.get("email"),
            "name": obj.get("name"),
            "metadata": obj.get("metadata", {}),
            "default_source": obj.get("default_source"),
        }
