"""Application configuration management."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    stripe_webhook_secret: str = Field(alias="STRIPE_WEBHOOK_SECRET")
    stripe_api_key: str = Field(default="", alias="STRIPE_API_KEY")

    solace_host: str = Field(alias="SOLACE_HOST")
    solace_semp_host: str = Field(default="", alias="SOLACE_SEMP_HOST")
    solace_semp_username: str = Field(default="", alias="SOLACE_SEMP_USERNAME")
    solace_semp_password: str = Field(default="", alias="SOLACE_SEMP_PASSWORD")
    solace_vpn: str = Field(alias="SOLACE_VPN")
    solace_username: str = Field(alias="SOLACE_USERNAME")
    solace_password: str = Field(alias="SOLACE_PASSWORD")
    solace_tls_enabled: bool = Field(default=False, alias="SOLACE_TLS_ENABLED")
    solace_tls_ca_cert_path: str = Field(default="", alias="SOLACE_TLS_CA_CERT_PATH")

    app_port: int = Field(default=8080, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    idempotency_ttl_seconds: int = Field(default=86_400, alias="IDEMPOTENCY_TTL_SECONDS")
    async_queue_size: int = Field(default=1_000, alias="ASYNC_QUEUE_SIZE")
    max_publish_retries: int = Field(default=3, alias="MAX_PUBLISH_RETRIES")
    retry_backoff_base_seconds: float = Field(default=0.5, alias="RETRY_BACKOFF_BASE_SECONDS")
    solace_message_ttl_ms: int = Field(default=0, alias="SOLACE_MESSAGE_TTL_MS")
    dmq_eligible: bool = Field(default=True, alias="DMQ_ELIGIBLE")
    async_shutdown_timeout_seconds: int = Field(default=10, alias="ASYNC_SHUTDOWN_TIMEOUT_SECONDS")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    e2e_stripe_account_id: str = Field(default="", alias="E2E_STRIPE_ACCOUNT_ID")
    e2e_consume_timeout_seconds: float = Field(default=10.0, alias="E2E_CONSUME_TIMEOUT_SECONDS")
    e2e_queue_drain_before_test: bool = Field(default=True, alias="E2E_QUEUE_DRAIN_BEFORE_TEST")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return memoized application settings."""

    return Settings()
