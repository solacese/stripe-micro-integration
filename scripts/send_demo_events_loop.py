#!/usr/bin/env python3
"""Send signed demo Stripe webhook events to the bridge at a fixed interval."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send signed demo webhook events repeatedly")
    parser.add_argument("--app-url", default="http://127.0.0.1:18080")
    parser.add_argument("--interval-seconds", type=float, default=10.0)
    parser.add_argument("--event-type", default="payment_intent.succeeded")
    parser.add_argument("--fixture", default="tests/fixtures/stripe_events/payment_intent.succeeded.json")
    parser.add_argument("--count", type=int, default=0, help="0 means infinite")
    return parser.parse_args()


def _build_signature(payload: bytes, secret: str) -> str:
    ts = int(time.time())
    signed = f"{ts}.{payload.decode('utf-8')}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def _load_fixture(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Fixture must contain a JSON object")
    return data


async def _run() -> int:
    args = _parse_args()
    settings = get_settings()

    webhook_secret = settings.stripe_webhook_secret
    account_id = settings.e2e_stripe_account_id or "acct_demo"

    fixture = _load_fixture(args.fixture)
    fixture["type"] = args.event_type

    sent = 0
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            if args.count > 0 and sent >= args.count:
                break

            event = dict(fixture)
            event["id"] = f"evt_loop_{uuid.uuid4().hex[:14]}"
            event["account"] = account_id
            event["created"] = int(time.time())

            payload = json.dumps(event, separators=(",", ":")).encode("utf-8")
            signature = _build_signature(payload, webhook_secret)

            response = await client.post(
                f"{args.app_url.rstrip('/')}/webhooks/stripe",
                content=payload,
                headers={"Stripe-Signature": signature},
            )

            sent += 1
            now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            print(
                f"[{now}] sent={sent} status={response.status_code} "
                f"event_id={event['id']} event_type={event['type']}"
            )

            if response.status_code != 200:
                print(f"response_body={response.text}")

            await asyncio.sleep(args.interval_seconds)

    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
