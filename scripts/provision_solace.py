#!/usr/bin/env python3
"""Idempotently provision Solace queues, subscriptions, and profiles via SEMP v2."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests


@dataclass(frozen=True)
class QueueDefinition:
    """Queue declaration with subscription topics."""

    name: str
    subscriptions: tuple[str, ...]


QUEUE_DEFINITIONS: tuple[QueueDefinition, ...] = (
    QueueDefinition("stripe.payments.inbound", ("stripe/webhook/v1/payment_intent/>",)),
    QueueDefinition("stripe.subscriptions.inbound", ("stripe/webhook/v1/subscription/>",)),
    QueueDefinition("stripe.invoices.inbound", ("stripe/webhook/v1/invoice/>",)),
    QueueDefinition("stripe.customers.inbound", ("stripe/webhook/v1/customer/>",)),
    QueueDefinition("stripe.all.inbound", ("stripe/webhook/v1/>",)),
    QueueDefinition("stripe.errors.dmq", ()),
)


def _normalize_semp_base(raw_host: str) -> str:
    """Normalize SEMP host to include /SEMP/v2/config once."""

    base = raw_host.rstrip("/")
    if base.endswith("/SEMP/v2/config"):
        return base
    if base.endswith("/SEMP/v2"):
        return f"{base}/config"
    return f"{base}/SEMP/v2/config"


class SEMPClient:
    """Simple SEMP v2 config API client."""

    def __init__(self, host: str, username: str, password: str, vpn: str) -> None:
        self._base = _normalize_semp_base(host)
        self._vpn = vpn
        self._session = requests.Session()
        self._session.auth = (username, password)
        self._session.headers.update({"Content-Type": "application/json"})

    def _url(self, path: str) -> str:
        return f"{self._base}/{path.lstrip('/')}"

    def _get(self, path: str) -> requests.Response:
        return self._session.get(self._url(path), timeout=20)

    def _post(self, path: str, payload: dict[str, Any]) -> requests.Response:
        return self._session.post(self._url(path), json=payload, timeout=20)

    @staticmethod
    def _is_not_found(response: requests.Response) -> bool:
        """Return True when SEMP response indicates resource-not-found."""

        if response.status_code == 404:
            return True
        if response.status_code != 400:
            return False
        try:
            body = response.json()
        except ValueError:
            return False
        status = (
            body.get("meta", {})
            .get("error", {})
            .get("status")
        )
        return status == "NOT_FOUND"

    def ensure_queue(self, queue_name: str) -> str:
        """Ensure queue exists and return status string."""

        encoded = quote(queue_name, safe="")
        queue_path = f"msgVpns/{quote(self._vpn, safe='')}/queues/{encoded}"
        response = self._get(queue_path)
        if response.status_code == 200:
            return "existing"
        if not self._is_not_found(response):
            response.raise_for_status()

        payload: dict[str, Any] = {
            "queueName": queue_name,
            "accessType": "non-exclusive",
            "maxMsgSpoolUsage": 5000,
            "maxRedeliveryCount": 5,
            "permission": "consume",
        }
        if queue_name != "stripe.errors.dmq":
            payload["deadMsgQueue"] = "stripe.errors.dmq"
        created = self._post(f"msgVpns/{quote(self._vpn, safe='')}/queues", payload)
        if created.status_code not in {200, 201}:
            created.raise_for_status()
        return "created"

    def ensure_subscription(self, queue_name: str, topic: str) -> str:
        """Ensure queue subscription exists and return status string."""

        vpn = quote(self._vpn, safe="")
        encoded_queue = quote(queue_name, safe="")
        encoded_topic = quote(topic, safe="")

        get_path = f"msgVpns/{vpn}/queues/{encoded_queue}/subscriptions/{encoded_topic}"
        response = self._get(get_path)
        if response.status_code == 200:
            return "existing"
        if not self._is_not_found(response):
            response.raise_for_status()

        payload = {"subscriptionTopic": topic}
        created = self._post(f"msgVpns/{vpn}/queues/{encoded_queue}/subscriptions", payload)
        if created.status_code not in {200, 201}:
            created.raise_for_status()
        return "created"

    def ensure_acl_profile(self, acl_name: str) -> str:
        """Ensure ACL profile exists and grants publish to target topic hierarchy."""

        vpn = quote(self._vpn, safe="")
        encoded_acl = quote(acl_name, safe="")
        profile_path = f"msgVpns/{vpn}/aclProfiles/{encoded_acl}"
        response = self._get(profile_path)
        if self._is_not_found(response):
            payload = {"aclProfileName": acl_name}
            created = self._post(f"msgVpns/{vpn}/aclProfiles", payload)
            if created.status_code not in {200, 201}:
                created.raise_for_status()
            status = "created"
        elif response.status_code == 200:
            status = "existing"
        else:
            response.raise_for_status()

        pub_topic_path = (
            f"msgVpns/{vpn}/aclProfiles/{encoded_acl}/publishTopicExceptions/"
            f"{quote('stripe/webhook/v1/>', safe='')}"
        )
        topic_check = self._get(pub_topic_path)
        if self._is_not_found(topic_check):
            payload = {"publishTopicException": "stripe/webhook/v1/>"}
            created = self._post(
                f"msgVpns/{vpn}/aclProfiles/{encoded_acl}/publishTopicExceptions",
                payload,
            )
            if created.status_code not in {200, 201}:
                created.raise_for_status()

        return status

    def ensure_client_profile(self, profile_name: str) -> str:
        """Ensure client profile exists."""

        vpn = quote(self._vpn, safe="")
        encoded_profile = quote(profile_name, safe="")
        profile_path = f"msgVpns/{vpn}/clientProfiles/{encoded_profile}"
        response = self._get(profile_path)
        if response.status_code == 200:
            return "existing"
        if not self._is_not_found(response):
            response.raise_for_status()

        payload = {"clientProfileName": profile_name}
        created = self._post(f"msgVpns/{vpn}/clientProfiles", payload)
        if created.status_code not in {200, 201}:
            created.raise_for_status()
        return "created"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Provision Solace queues and profiles")
    parser.add_argument("--semp-host", default=os.getenv("SOLACE_SEMP_HOST", ""))
    parser.add_argument("--username", default=os.getenv("SOLACE_SEMP_USERNAME", ""))
    parser.add_argument("--password", default=os.getenv("SOLACE_SEMP_PASSWORD", ""))
    parser.add_argument("--vpn", default=os.getenv("SOLACE_VPN", "default"))
    return parser.parse_args()


def _validate_args(args: argparse.Namespace) -> None:
    missing: list[str] = []
    for field in ["semp_host", "username", "password", "vpn"]:
        if not getattr(args, field):
            missing.append(field)
    if missing:
        raise ValueError(f"Missing required provisioning arguments: {', '.join(missing)}")


def main() -> int:
    """Provision Solace resources and print summary table."""

    args = _parse_args()
    _validate_args(args)

    client = SEMPClient(args.semp_host, args.username, args.password, args.vpn)

    queue_rows: list[tuple[str, str, str]] = []
    subscription_rows: list[tuple[str, str, str]] = []

    for definition in QUEUE_DEFINITIONS:
        status = client.ensure_queue(definition.name)
        queue_rows.append((definition.name, "queue", status))
        for subscription in definition.subscriptions:
            sub_status = client.ensure_subscription(definition.name, subscription)
            subscription_rows.append((definition.name, subscription, sub_status))

    acl_status = client.ensure_acl_profile("stripe-bridge-acl")
    client_profile_status = client.ensure_client_profile("stripe-bridge-client-profile")

    print("\nSolace Provisioning Summary")
    print("=" * 72)
    print(f"{'Resource':35} {'Type':20} {'Status':12}")
    print("-" * 72)
    for resource, kind, status in queue_rows:
        print(f"{resource:35} {kind:20} {status:12}")
    print("-" * 72)
    for queue_name, topic, status in subscription_rows:
        print(f"{queue_name:35} {topic:20} {status:12}")
    print("-" * 72)
    print(f"{'stripe-bridge-acl':35} {'acl_profile':20} {acl_status:12}")
    print(f"{'stripe-bridge-client-profile':35} {'client_profile':20} {client_profile_status:12}")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Provisioning failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
