from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from monitoring.event_bus import MonitoringEventBus
from monitoring.health import HealthRegistry
from monitoring.models import (
    AuditActivityResponse,
    FailuresResponse,
    MetricsResponse,
    SystemHealthResponse,
    TransactionsResponse,
)
from monitoring.store import MonitoringStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


def _get_store(request: Request) -> MonitoringStore:
    return request.app.state.monitoring_store


def _get_health(request: Request) -> HealthRegistry:
    return request.app.state.monitoring_health


def _get_bus(request: Request) -> MonitoringEventBus:
    return request.app.state.monitoring_event_bus


@router.get("/health", response_model=SystemHealthResponse)
def get_health(request: Request) -> SystemHealthResponse:
    health = _get_health(request)
    services = health.snapshot()
    return SystemHealthResponse(
        overall_status=health.overall_status(),
        services=services,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/metrics", response_model=MetricsResponse)
def get_metrics(request: Request) -> MetricsResponse:
    store = _get_store(request)
    health = _get_health(request)
    return MetricsResponse(
        overview=store.overview(health.overall_status()),
        payments=store.payment_metrics(),
        performance=store.performance_metrics(),
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/transactions", response_model=TransactionsResponse)
def get_transactions(request: Request, limit: int = 100) -> TransactionsResponse:
    store = _get_store(request)
    return TransactionsResponse(transactions=store.transactions(limit=limit))


@router.get("/failures", response_model=FailuresResponse)
def get_failures(request: Request, limit: int = 50) -> FailuresResponse:
    store = _get_store(request)
    return FailuresResponse(
        summary=store.failure_summary(),
        recent_failures=store.recent_failures(limit=limit),
    )


@router.get("/audit-events", response_model=AuditActivityResponse)
def get_audit_events(request: Request, limit: int = 100) -> AuditActivityResponse:
    store = _get_store(request)
    return AuditActivityResponse(events=store.audit_activity(limit=limit))


@router.get("/alerts")
def get_alerts(request: Request) -> dict:
    store = _get_store(request)
    return {"alerts": [a.model_dump(mode="json") for a in store.alerts()]}


@router.websocket("/ws")
async def monitoring_ws(websocket: WebSocket) -> None:
    """Live monitoring event stream.

    On connect, does NOT replay history (REST already covers "current
    state" - see GET /monitoring/metrics etc.); it only forwards events
    published to MonitoringEventBus from this point on, plus a periodic
    heartbeat so the dashboard's connection indicator can tell "connected
    and idle" apart from "silently dead".
    """
    bus: MonitoringEventBus = websocket.app.state.monitoring_event_bus
    await websocket.accept()
    queue = await bus.subscribe()
    try:
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=20.0)
                await websocket.send_json(message)
            except asyncio.TimeoutError:
                await websocket.send_json({"event": "ping", "data": {"ts": datetime.now(timezone.utc).isoformat()}})
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        logger.exception("monitoring websocket connection ended unexpectedly")
    finally:
        await bus.unsubscribe(queue)
