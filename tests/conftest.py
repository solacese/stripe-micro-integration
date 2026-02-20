"""Common pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.config import Settings

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "stripe_events"


@pytest.fixture
def fixture_dir() -> Path:
    """Return Stripe fixture directory path."""

    return FIXTURES_DIR


@pytest.fixture
def load_fixture(fixture_dir: Path):
    """Load Stripe event fixture by filename."""

    def _loader(filename: str) -> dict[str, Any]:
        with (fixture_dir / filename).open("r", encoding="utf-8") as fh:
            return json.load(fh)

    return _loader


@pytest.fixture
def make_settings():
    """Create Settings objects with override support for tests."""

    def _factory(**overrides: Any) -> Settings:
        base: dict[str, Any] = {
            "STRIPE_WEBHOOK_SECRET": "whsec_test",
            "STRIPE_API_KEY": "sk_test",
            "SOLACE_HOST": "tcp://localhost:55555",
            "SOLACE_SEMP_HOST": "http://localhost:8080",
            "SOLACE_SEMP_USERNAME": "admin",
            "SOLACE_SEMP_PASSWORD": "admin",
            "SOLACE_VPN": "default",
            "SOLACE_USERNAME": "user",
            "SOLACE_PASSWORD": "pass",
            "SOLACE_TLS_ENABLED": False,
            "SOLACE_TLS_CA_CERT_PATH": "",
            "APP_PORT": 8080,
            "REDIS_URL": "redis://localhost:6379/0",
            "E2E_STRIPE_ACCOUNT_ID": "acct_test",
        }
        base.update(overrides)
        return Settings(**base)

    return _factory
