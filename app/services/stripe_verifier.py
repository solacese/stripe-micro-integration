"""Stripe webhook signature verification."""

from __future__ import annotations

from typing import Any

import stripe


class WebhookVerificationError(ValueError):
    """Raised when Stripe webhook verification fails."""


class StripeVerifier:
    """Validate and parse Stripe webhook payloads."""

    def __init__(self, webhook_secret: str) -> None:
        self._webhook_secret = webhook_secret

    def verify(self, payload: bytes, signature_header: str | None) -> dict[str, Any]:
        """Verify payload/signature and return parsed event data."""

        if not signature_header:
            raise WebhookVerificationError("Missing Stripe-Signature header")

        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=signature_header,
                secret=self._webhook_secret,
            )  # type: ignore[no-untyped-call]
        except Exception as exc:
            raise WebhookVerificationError(str(exc)) from exc

        if not isinstance(event, dict):
            return dict(event)
        return event
