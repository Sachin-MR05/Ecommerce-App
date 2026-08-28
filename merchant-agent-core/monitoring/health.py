from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from monitoring.models import ServiceHealth, ServiceStatus

# Fixed set of logical services this system reports on. Matches the
# components named throughout merchant-agent-core (README.md's own
# component list) - "database" stands in for the Java Tool Layer, which is
# where this service's persistence actually lives (see
# audit/audit_repository.py's module docstring).
AGENT_GATEWAY = "agent_gateway"
MERCHANT_AGENT = "merchant_agent"
TRANSACTION_ORCHESTRATOR = "transaction_orchestrator"
PAYMENT_SERVICE = "payment_service"
FAILURE_HANDLING = "failure_handling"
AUDIT_SERVICE = "audit_service"
MONITORING_SERVICE = "monitoring_service"
DATABASE = "database"

ALL_SERVICES = (
    AGENT_GATEWAY,
    MERCHANT_AGENT,
    TRANSACTION_ORCHESTRATOR,
    PAYMENT_SERVICE,
    FAILURE_HANDLING,
    AUDIT_SERVICE,
    MONITORING_SERVICE,
    DATABASE,
)

# A service with no heartbeat inside this window is DEGRADED; beyond
# twice this window it is DOWN. Static/self-hosted services (this process
# itself) heartbeat on every metrics poll, so in practice they never age
# out; only DATABASE (an external dependency, pinged periodically - see
# wiring.py) genuinely exercises this staleness path.
HEARTBEAT_STALE_SECONDS = 30.0


@dataclass
class _HealthRecord:
    status: ServiceStatus
    latency_ms: Optional[float]
    last_heartbeat: float  # monotonic seconds
    last_heartbeat_wall: datetime
    started_at: float
    detail: Optional[str] = None


class HealthRegistry:
    """Thread-safe, in-memory health state for every logical service.

    Deliberately dumb: it only stores what the last heartbeat said. It
    never decides *why* a service is degraded - callers (wiring.py) decide
    that and call `report()`. This mirrors FailureHandler/AuditService:
    small, single-purpose, no cross-cutting business logic.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, _HealthRecord] = {}
        now = time.monotonic()
        now_wall = datetime.now(timezone.utc)
        for service in ALL_SERVICES:
            self._records[service] = _HealthRecord(
                status=ServiceStatus.UNKNOWN,
                latency_ms=None,
                last_heartbeat=now,
                last_heartbeat_wall=now_wall,
                started_at=now,
            )

    def report(
        self,
        service: str,
        status: ServiceStatus,
        latency_ms: Optional[float] = None,
        detail: Optional[str] = None,
    ) -> bool:
        """Record a heartbeat. Returns True if this changed the service's
        status (so the caller can decide whether to broadcast/alert)."""
        now = time.monotonic()
        now_wall = datetime.now(timezone.utc)
        with self._lock:
            existing = self._records.get(service)
            changed = existing is None or existing.status != status
            started_at = existing.started_at if existing and existing.status == status else now
            self._records[service] = _HealthRecord(
                status=status,
                latency_ms=latency_ms,
                last_heartbeat=now,
                last_heartbeat_wall=now_wall,
                started_at=started_at,
                detail=detail,
            )
        return changed

    def snapshot(self) -> list[ServiceHealth]:
        now = time.monotonic()
        results: list[ServiceHealth] = []
        with self._lock:
            for service, record in self._records.items():
                status = record.status
                age = now - record.last_heartbeat
                if status == ServiceStatus.UP and age > HEARTBEAT_STALE_SECONDS * 2:
                    status = ServiceStatus.DOWN
                elif status == ServiceStatus.UP and age > HEARTBEAT_STALE_SECONDS:
                    status = ServiceStatus.DEGRADED
                results.append(
                    ServiceHealth(
                        service=service,
                        status=status,
                        latency_ms=record.latency_ms,
                        last_heartbeat=record.last_heartbeat_wall,
                        uptime_seconds=max(0.0, now - record.started_at),
                        detail=record.detail,
                    )
                )
        return results

    def overall_status(self) -> ServiceStatus:
        statuses = [s.status for s in self.snapshot()]
        if any(s == ServiceStatus.DOWN for s in statuses):
            return ServiceStatus.DOWN
        if any(s == ServiceStatus.DEGRADED for s in statuses):
            return ServiceStatus.DEGRADED
        if all(s == ServiceStatus.UP for s in statuses):
            return ServiceStatus.UP
        return ServiceStatus.UNKNOWN
