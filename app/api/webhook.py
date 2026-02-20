"""Stripe webhook endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from app.metrics import (
    stripe_webhooks_invalid_signature_total,
    stripe_webhooks_received_total,
    stripe_webhooks_verified_total,
)
from app.services.stripe_verifier import WebhookVerificationError

router = APIRouter(tags=["webhook"])


@router.post("/webhooks/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    response: Response,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> dict[str, bool]:
    """Receive, verify, and enqueue Stripe webhook event."""

    body = await request.body()

    verifier = request.app.state.stripe_verifier
    processor = request.app.state.async_processor

    try:
        event = verifier.verify(body, stripe_signature)
    except WebhookVerificationError as exc:
        stripe_webhooks_invalid_signature_total.inc()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    event_type = str(event.get("type", "unknown"))
    stripe_webhooks_received_total.labels(event_type=event_type).inc()
    stripe_webhooks_verified_total.inc()

    queued = processor.enqueue(event)
    if not queued:
        response.headers["Retry-After"] = "5"
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Queue is full")

    return {"received": True}
