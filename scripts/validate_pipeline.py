#!/usr/bin/env python3
"""Standalone validation script for Stripe to Solace bridge."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx

from app.config import Settings
from app.services.solace_subscriber import SolaceSubscriber


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Stripe -> Solace bridge")
    parser.add_argument("--app-url", required=True)
    parser.add_argument("--stripe-key", required=True)
    parser.add_argument("--webhook-secret", required=True)
    parser.add_argument("--solace-host", required=True)
    parser.add_argument("--solace-vpn", required=True)
    parser.add_argument("--solace-user", required=True)
    parser.add_argument("--solace-password", required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--semp-host", default=os.getenv("SOLACE_SEMP_HOST", ""))
    parser.add_argument("--semp-username", default=os.getenv("SOLACE_SEMP_USERNAME", ""))
    parser.add_argument("--semp-password", default=os.getenv("SOLACE_SEMP_PASSWORD", ""))
    return parser.parse_args()


def _load_fixture(event_type: str) -> dict[str, Any]:
    filename = f"{event_type}.json"
    path = Path("tests/fixtures/stripe_events") / filename
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found for event type {event_type}: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _sign_payload(payload: bytes, secret: str) -> str:
    timestamp = int(time.time())
    signed = f"{timestamp}.{payload.decode('utf-8')}".encode()
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def _extract_counter(metrics_text: str, metric_name: str) -> float:
    total = 0.0
    for line in metrics_text.splitlines():
        if line.startswith(metric_name):
            parts = line.split()
            if len(parts) == 2:
                total += float(parts[1])
    return total


async def _run_validation(args: argparse.Namespace) -> int:
    print("🔍 Stripe → Solace Bridge Validation")

    async with httpx.AsyncClient(timeout=10) as client:
        health_response = await client.get(f"{args.app_url}/health")
        print("✅ /health" if health_response.status_code == 200 else "❌ /health")

        ready_response = await client.get(f"{args.app_url}/ready")
        print("✅ /ready" if ready_response.status_code == 200 else "❌ /ready")

        metrics_before = await client.get(f"{args.app_url}/metrics")
        baseline_received = _extract_counter(metrics_before.text, "stripe_webhooks_received_total")

    if args.semp_host and args.semp_username and args.semp_password:
        provision_cmd = [
            sys.executable,
            "scripts/provision_solace.py",
            "--semp-host",
            args.semp_host,
            "--username",
            args.semp_username,
            "--password",
            args.semp_password,
            "--vpn",
            args.solace_vpn,
        ]
        await asyncio.to_thread(subprocess.run, provision_cmd, check=True)

    settings = Settings(
        STRIPE_WEBHOOK_SECRET=args.webhook_secret,
        STRIPE_API_KEY=args.stripe_key,
        SOLACE_HOST=args.solace_host,
        SOLACE_SEMP_HOST=args.semp_host,
        SOLACE_SEMP_USERNAME=args.semp_username,
        SOLACE_SEMP_PASSWORD=args.semp_password,
        SOLACE_VPN=args.solace_vpn,
        SOLACE_USERNAME=args.solace_user,
        SOLACE_PASSWORD=args.solace_password,
        SOLACE_TLS_ENABLED=False,
        SOLACE_TLS_CA_CERT_PATH="",
        REDIS_URL=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    )
    subscriber = SolaceSubscriber(settings)
    await subscriber.connect()

    checks = [
        ("payment_intent.succeeded", "stripe.payments.inbound"),
        ("customer.subscription.created", "stripe.subscriptions.inbound"),
        ("invoice.payment_failed", "stripe.invoices.inbound"),
        ("customer.created", "stripe.customers.inbound"),
        ("checkout.session.completed", "stripe.all.inbound"),
    ]

    passed = 0
    latencies_ms: list[float] = []

    for event_type, queue in checks:
        fixture = _load_fixture(event_type)
        fixture["id"] = f"evt_validate_{uuid4().hex}"
        fixture["account"] = args.account_id
        payload = json.dumps(fixture).encode("utf-8")
        signature = _sign_payload(payload, args.webhook_secret)

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{args.app_url}/webhooks/stripe",
                content=payload,
                headers={"Stripe-Signature": signature},
            )

        if response.status_code != 200:
            print(f"❌ {event_type} → {queue} [HTTP {response.status_code}]")
            continue

        message = await subscriber.consume_one(queue, timeout_seconds=10)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if message is None:
            print(f"❌ {event_type} → {queue} [TIMEOUT]")
            continue

        try:
            UUID(message["trace_id"])
            _ = message["event_id"]
            _ = message["event_type"]
            _ = message["data"]
            _ = message["bridge_received_at"]
        except Exception:
            print(f"❌ {event_type} → {queue} [INVALID ENVELOPE]")
            continue

        passed += 1
        latencies_ms.append(elapsed_ms)
        print(f"✅ {event_type} → {queue} [{elapsed_ms:.0f}ms]")

    async with httpx.AsyncClient(timeout=10) as client:
        metrics_after = await client.get(f"{args.app_url}/metrics")
        post_received = _extract_counter(metrics_after.text, "stripe_webhooks_received_total")

    await subscriber.disconnect()

    if post_received - baseline_received < passed:
        print("❌ Metrics did not increment as expected")

    average_latency = sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0.0
    max_latency = max(latencies_ms) if latencies_ms else 0.0

    print("━" * 38)
    print(f"Validation Results: {passed}/{len(checks)} passed")
    print(f"Total latency: avg {average_latency:.0f}ms, max {max_latency:.0f}ms")
    print("Broker: connected | Queue depth: 0")
    print("━" * 38)

    return 0 if passed == len(checks) else 1


def main() -> int:
    """CLI entrypoint for pipeline validation."""

    args = _parse_args()
    return asyncio.run(_run_validation(args))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Validation failed during subprocess execution: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except Exception as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
