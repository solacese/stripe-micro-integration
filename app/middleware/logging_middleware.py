"""Request logging middleware."""

from __future__ import annotations

from time import perf_counter
from typing import cast

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log inbound HTTP requests with structured fields."""

    def __init__(self, app) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._logger = structlog.get_logger("http")

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        start = perf_counter()
        response = cast(Response, await call_next(request))
        duration_ms = (perf_counter() - start) * 1000
        self._logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 3),
        )
        return response
