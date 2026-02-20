"""HTTP metrics middleware."""

from __future__ import annotations

from time import perf_counter
from typing import cast

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.metrics import http_request_duration_seconds


class MetricsMiddleware(BaseHTTPMiddleware):
    """Collect request duration metrics for HTTP traffic."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        start = perf_counter()
        response = cast(Response, await call_next(request))
        elapsed = max(0.0, perf_counter() - start)
        http_request_duration_seconds.labels(
            method=request.method,
            path=request.url.path,
            status_code=str(response.status_code),
        ).observe(elapsed)
        return response
