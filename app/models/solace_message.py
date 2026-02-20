"""Solace message metadata models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SolaceMessageMetadata(BaseModel):
    """Metadata extracted from a consumed Solace message."""

    destination: str | None = None
    correlation_id: str | None = None
    application_message_id: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
