"""Stripe event normalization models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StripeEventEnvelope(BaseModel):
    """Normalized envelope published to Solace."""

    event_id: str
    event_type: str
    api_version: str | None = None
    account_id: str
    created_at: int
    bridge_received_at: str
    bridge_version: str
    trace_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)
