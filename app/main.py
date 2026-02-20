"""ASGI entrypoint for Stripe Solace bridge."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.webhook import router as webhook_router
from app.config import Settings, get_settings
from app.lifespan import app_lifespan
from app.logging import configure_logging
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.metrics_middleware import MetricsMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure FastAPI application."""

    runtime_settings = settings or get_settings()
    configure_logging(runtime_settings.log_level)

    app = FastAPI(title="stripe-solace-bridge", version="1.0.0", lifespan=app_lifespan)
    app.state.settings = runtime_settings

    app.add_middleware(LoggingMiddleware)
    app.add_middleware(MetricsMiddleware)

    app.include_router(webhook_router)
    app.include_router(health_router)

    return app


app = create_app()
