from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from audit.audit_event import AuditEvent, AuditEventType
from audit.audit_service import AuditService
from monitoring import alerts as alert_rules
from monitoring import health as health_names
from monitoring.event_bus import (
    EVENT_ALERT_CREATED,
    EVENT_ALERT_RESOLVED,
    EVENT_AUDIT_EVENT,
    EVENT_FAILURE_CREATED,
    EVENT_METRICS_UPDATED,
    EVENT_SERVICE_HEALTH_CHANGED,
    EVENT_TRANSACTION_UPDATED,
    MonitoringEventBus,
)
from monitoring.health import HealthRegistry
from monitoring.models import ServiceStatus
from monitoring.store import MonitoringStore
from monitoring.routes import router as monitoring_router
from transaction.transaction_orchestrator import TransactionOrchestrator

logger = logging.getLogger(__name__)

# Poll/refresh intervals, seconds. Short enough that the dashboard feels
# live, long enough not to busy-loop a dev machine.
_TRANSACTION_POLL_INTERVAL = 2.0
_ALERT_EVAL_INTERVAL = 5.0
_SELF_HEARTBEAT_INTERVAL = 5.0
_DATABASE_PING_INTERVAL = 10.0
_DATABASE_PING_TIMEOUT = 3.0

# In-process components heartbeat themselves as UP on every interval tick
# simply because this FastAPI process is running - there is no separate
# process boundary to fail independently. DATABASE is the one exception
# (see _ping_database below): it is the Java Tool Layer, a real network
# dependency, and its health is only ever known by actually calling it.
_SELF_HOSTED_SERVICES = (
    health_names.AGENT_GATEWAY,
    health_names.MERCHANT_AGENT,
    health_names.TRANSACTION_ORCHESTRATOR,
    health_names.PAYMENT_SERVICE,
    health_names.FAILURE_HANDLING,
    health_names.AUDIT_SERVICE,
    health_names.MONITORING_SERVICE,
)


class _ApiLatencyMiddleware(BaseHTTPMiddleware):
    """Feeds MonitoringStore's request-rate/API-latency metrics. Purely
    observational - never inspects or modifies the request/response body,
    and runs independently of app/gateway/middleware.py's own structured
    access log."""

    async def dispatch(self, request: Request, call_next) -> Response:
        store: MonitoringStore = request.app.state.monitoring_store
        start = time.perf_counter()
        store.record_request()
        response = await call_next(request)
        store.record_api_latency((time.perf_counter() - start) * 1000)
        return response


def include_monitoring(
    app: FastAPI,
    audit_service: AuditService,
    transaction_orchestrator: TransactionOrchestrator,
    tool_service_url: Optional[str] = None,
    dashboard_cors_origins: str = "http://localhost:5173",
    store: Optional[MonitoringStore] = None,
) -> None:
    """One-call integration point, mirroring app/gateway/wiring.py.

    Mounts every GET /monitoring/* route and the /monitoring/ws WebSocket,
    subscribes to `audit_service` as a read-only observer (see
    AuditService.add_listener), and starts background tasks that poll
    `transaction_orchestrator` and (optionally) ping the Java Tool Layer
    for the "database" health entry. Never calls into audit_service,
    transaction_orchestrator, or any FailureHandler/PaymentService method
    that mutates state - this module is read-only by construction.
    """

    store = store or MonitoringStore()
    health = HealthRegistry()
    bus = MonitoringEventBus()

    app.state.monitoring_store = store
    app.state.monitoring_health = health
    app.state.monitoring_event_bus = bus

    app.include_router(monitoring_router)
    app.add_middleware(_ApiLatencyMiddleware)

    origins = [o.strip() for o in dashboard_cors_origins.split(",") if o.strip()] or ["http://localhost:5173"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    loop_holder: dict[str, asyncio.AbstractEventLoop] = {}

    def _on_audit_event(event: AuditEvent) -> None:
        # Called synchronously from whatever thread recorded the event
        # (see AuditService.record_event) - never awaited, never blocks
        # the caller beyond this in-memory bookkeeping.
        new_failure = store.on_audit_event(event)
        loop = loop_holder.get("loop")
        if loop is None:
            return
        bus.publish_threadsafe(
            loop,
            EVENT_AUDIT_EVENT,
            {
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type.value,
                "transaction_id": event.transaction_id,
                "status": event.status,
            },
        )
        if event.event_type == AuditEventType.RECOVERY_COMPLETED:
            store.note_recovery_outcome(event)
        if new_failure is not None:
            bus.publish_threadsafe(loop, EVENT_FAILURE_CREATED, new_failure.model_dump(mode="json"))
        if event.transaction_id:
            bus.publish_threadsafe(
                loop,
                EVENT_TRANSACTION_UPDATED,
                {"transaction_id": event.transaction_id, "status": event.status},
            )

    audit_service.add_listener(_on_audit_event)

    async def _poll_transactions() -> None:
        while True:
            try:
                store.set_transaction_records(transaction_orchestrator.list_transactions())
            except Exception:  # noqa: BLE001
                logger.exception("monitoring: failed to poll transaction records")
            await asyncio.sleep(_TRANSACTION_POLL_INTERVAL)

    async def _self_heartbeat() -> None:
        while True:
            for service in _SELF_HOSTED_SERVICES:
                health.report(service, ServiceStatus.UP, latency_ms=0.0)
            await asyncio.sleep(_SELF_HEARTBEAT_INTERVAL)

    async def _ping_database() -> None:
        if not tool_service_url:
            health.report(health_names.DATABASE, ServiceStatus.UNKNOWN, detail="TOOL_SERVICE_URL not configured")
            return
        async with httpx.AsyncClient(timeout=_DATABASE_PING_TIMEOUT) as client:
            while True:
                start = time.perf_counter()
                try:
                    response = await client.get(tool_service_url)
                    latency_ms = (time.perf_counter() - start) * 1000
                    store.record_database_latency(latency_ms)
                    status = ServiceStatus.UP if response.status_code < 500 else ServiceStatus.DEGRADED
                    health.report(health_names.DATABASE, status, latency_ms=latency_ms)
                except Exception as exc:  # noqa: BLE001
                    health.report(health_names.DATABASE, ServiceStatus.DOWN, detail=str(exc)[:200])
                await asyncio.sleep(_DATABASE_PING_INTERVAL)

    async def _evaluate_alerts_and_health() -> None:
        while True:
            try:
                changed_health: list[tuple[str, str, ServiceStatus]] = []
                for svc_health in health.snapshot():
                    result = alert_rules.evaluate_service_health_alert(store, svc_health.service, svc_health.status)
                    if result:
                        key, alert = result
                        loop = loop_holder.get("loop")
                        if loop:
                            event_name = EVENT_ALERT_CREATED if alert.status.value == "ACTIVE" else EVENT_ALERT_RESOLVED
                            bus.publish_threadsafe(loop, event_name, alert.model_dump(mode="json"))
                    changed_health.append((svc_health.service, svc_health.status.value, svc_health.status))

                overall = health.overall_status()
                for key, alert in alert_rules.evaluate_alerts(store, overall):
                    loop = loop_holder.get("loop")
                    if loop:
                        event_name = EVENT_ALERT_CREATED if alert.status.value == "ACTIVE" else EVENT_ALERT_RESOLVED
                        bus.publish_threadsafe(loop, event_name, alert.model_dump(mode="json"))

                loop = loop_holder.get("loop")
                if loop:
                    bus.publish_threadsafe(
                        loop,
                        EVENT_METRICS_UPDATED,
                        {"overview": store.overview(overall).model_dump(mode="json")},
                    )
                    for service, status_value, _status in changed_health:
                        bus.publish_threadsafe(
                            loop, EVENT_SERVICE_HEALTH_CHANGED, {"service": service, "status": status_value}
                        )
            except Exception:  # noqa: BLE001
                logger.exception("monitoring: alert evaluation failed")
            await asyncio.sleep(_ALERT_EVAL_INTERVAL)

    background_tasks: list[asyncio.Task] = []

    @app.on_event("startup")
    async def _start_monitoring_background_tasks() -> None:
        loop_holder["loop"] = asyncio.get_running_loop()
        for service in _SELF_HOSTED_SERVICES:
            health.report(service, ServiceStatus.UP, latency_ms=0.0)
        background_tasks.append(asyncio.create_task(_poll_transactions()))
        background_tasks.append(asyncio.create_task(_self_heartbeat()))
        background_tasks.append(asyncio.create_task(_ping_database()))
        background_tasks.append(asyncio.create_task(_evaluate_alerts_and_health()))
        logger.info("Monitoring module started (dashboard CORS origins: %s)", origins)

    @app.on_event("shutdown")
    async def _stop_monitoring_background_tasks() -> None:
        for task in background_tasks:
            task.cancel()
