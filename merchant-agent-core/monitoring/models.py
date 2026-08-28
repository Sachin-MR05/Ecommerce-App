from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ServiceStatus(str, Enum):
    UP = "UP"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


class ServiceHealth(BaseModel):
    """Point-in-time health of one logical service in the Merchant Agent
    system. `service` is a fixed, small vocabulary (see health.py) - never
    a free-form string - so the dashboard can render a stable panel."""

    model_config = ConfigDict(populate_by_name=True)

    service: str
    status: ServiceStatus
    latency_ms: Optional[float] = None
    last_heartbeat: Optional[datetime] = None
    uptime_seconds: Optional[float] = None
    detail: Optional[str] = None


class SystemHealthResponse(BaseModel):
    overall_status: ServiceStatus
    services: list[ServiceHealth]
    generated_at: datetime


class SystemOverview(BaseModel):
    """GET /monitoring/metrics -> overview section."""

    system_status: ServiceStatus
    total_transactions: int
    successful_transactions: int
    failed_transactions: int
    pending_transactions: int
    active_transactions: int
    success_rate: float
    avg_transaction_duration_ms: Optional[float] = None


class PaymentMetrics(BaseModel):
    payment_attempts: int
    successful_payments: int
    failed_payments: int
    payment_timeouts: int
    payment_success_rate: float
    avg_payment_latency_ms: Optional[float] = None
    # Bucketed time series for the "payment success/failure over time" chart.
    # Each bucket is a fixed-width window (see store.py: PAYMENT_BUCKET_SECONDS).
    timeline: list["PaymentTimelineBucket"] = Field(default_factory=list)


class PaymentTimelineBucket(BaseModel):
    bucket_start: datetime
    successful: int
    failed: int
    timed_out: int


class FailureSummary(BaseModel):
    total_failures: int
    failures_by_service: dict[str, int]
    retry_count: int
    retry_success_rate: Optional[float] = None
    unrecoverable_failures: int
    trend: list["FailureTrendBucket"] = Field(default_factory=list)


class FailureTrendBucket(BaseModel):
    bucket_start: datetime
    count: int


class FailureRecord(BaseModel):
    failure_id: str
    transaction_id: Optional[str] = None
    service: str
    error_type: str
    error_message: Optional[str] = None
    retry_count: int = 0
    recovery_status: str = "UNKNOWN"
    timestamp: datetime


class FailuresResponse(BaseModel):
    summary: FailureSummary
    recent_failures: list[FailureRecord]


class PerformanceMetrics(BaseModel):
    api_latency_ms: Optional[float] = None
    transaction_latency_ms: Optional[float] = None
    payment_latency_ms: Optional[float] = None
    database_latency_ms: Optional[float] = None
    llm_latency_ms: Optional[float] = None
    request_rate_per_min: float = 0.0
    latency_timeline: list["LatencyTimelineBucket"] = Field(default_factory=list)


class LatencyTimelineBucket(BaseModel):
    bucket_start: datetime
    api_latency_ms: Optional[float] = None
    transaction_latency_ms: Optional[float] = None
    payment_latency_ms: Optional[float] = None
    request_count: int = 0


class MetricsResponse(BaseModel):
    overview: SystemOverview
    payments: PaymentMetrics
    performance: PerformanceMetrics
    generated_at: datetime


class TransactionSnapshot(BaseModel):
    """Read-only observability view of one transaction. Derived entirely
    from TransactionOrchestrator.list_transactions() (authoritative state,
    amount, currency) plus the Audit Service's event stream (timestamps) -
    never a second source of truth for business state."""

    transaction_id: str
    session_id: Optional[str] = None
    transaction_type: str = "checkout"
    state: str
    status: str
    amount: Optional[int] = None
    currency: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None


class TransactionsResponse(BaseModel):
    transactions: list[TransactionSnapshot]


class AuditActivityItem(BaseModel):
    timestamp: datetime
    event_type: str
    transaction_id: Optional[str] = None
    service: str
    status: str


class AuditActivityResponse(BaseModel):
    events: list[AuditActivityItem]


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"


class Alert(BaseModel):
    alert_id: str
    severity: AlertSeverity
    title: str
    description: str
    affected_service: str
    timestamp: datetime
    status: AlertStatus


class AlertsResponse(BaseModel):
    alerts: list[Alert]


class MonitoringWSEvent(BaseModel):
    """Envelope for every message sent over /monitoring/ws. `event` is one
    of the fixed event names in event_bus.py; `data` is one of the models
    above (serialized), kept intentionally small per message."""

    event: str
    data: dict[str, Any]
