"""Health, readiness, and metrics endpoints."""

from __future__ import annotations

from time import monotonic

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.metrics import render_metrics

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    """Return liveness status."""

    started_at = request.app.state.started_at
    return {"status": "ok", "uptime_seconds": round(monotonic() - started_at, 3)}


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    """Return readiness based on Solace connectivity."""

    publisher = request.app.state.solace_publisher
    if publisher.is_connected:
        return JSONResponse({"status": "ready"}, status_code=status.HTTP_200_OK)
    return JSONResponse({"status": "not_ready"}, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


@router.get("/metrics")
async def metrics() -> Response:
    """Return Prometheus metrics payload."""

    return render_metrics()
