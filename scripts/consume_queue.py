#!/usr/bin/env python3
"""Consume messages from a Solace durable queue."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime

from app.config import get_settings
from app.services.solace_subscriber import SolaceSubscriber


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consume Solace queue messages")
    parser.add_argument("--queue", required=True, help="Queue name to consume")
    parser.add_argument("--count", type=int, default=1, help="Maximum number of messages")
    parser.add_argument("--timeout", type=float, default=30.0, help="Overall timeout in seconds")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON payload")
    parser.add_argument("--ack", action="store_true", help="ACK messages (default browse mode)")
    return parser.parse_args()


async def _run() -> int:
    args = _parse_args()
    settings = get_settings()
    subscriber = SolaceSubscriber(settings)

    try:
        await subscriber.connect()
        messages = await subscriber.consume_n(
            queue_name=args.queue,
            n=args.count,
            timeout_seconds=args.timeout,
            ack=args.ack,
            include_meta=True,
        )

        if not messages:
            print("No messages received.")
            return 0

        for index, message in enumerate(messages, start=1):
            ts = datetime.now(UTC).isoformat()
            output = message
            if args.pretty:
                payload = json.dumps(output, indent=2, sort_keys=True)
            else:
                payload = json.dumps(output)
            print(f"[{ts}] message={index} queue={args.queue}")
            print(payload)

        if not args.ack:
            print("Browse mode active: use --ack to acknowledge messages.")

        return 0
    finally:
        await subscriber.disconnect()


if __name__ == "__main__":
    try:
        import asyncio

        raise SystemExit(asyncio.run(_run()))
    except KeyboardInterrupt as exc:
        raise SystemExit(130) from exc
    except Exception as exc:
        print(f"consume_queue failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
