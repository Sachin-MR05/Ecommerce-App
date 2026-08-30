from __future__ import annotations

import statistics
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from audit.audit_event import AuditEvent, AuditEventType
from monitoring.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    AuditActivityItem,
    FailureRecord,
    FailureSummary,
    FailureTrendBucket,
    LatencyTimelineBucket,
    PaymentMetrics,
    PaymentTimelineBucket,
    PerformanceMetrics,
    ServiceStatus,
    SystemOverview,
    TransactionSnapshot,
)
from transaction.transaction_store import TransactionRecord

# Bucket width for the time-series charts (payment success/failure,
# failure trend, latency/throughput). A fixed, small width keeps the
# in-memory history bounded (see MAX_BUCKETS) without a real time-series
# database - acceptable for a single-process dev/staging monitoring view;
# swap MonitoringStore's bucket dicts for a real TSDB query before relying
# on this across a long-running production deployment.
BUCKET_SECONDS = 60
MAX_BUCKETS = 60  # 1 hour of history at 1-minute buckets
MAX_RECENT_ITEMS = 200

_TRANSACTION_LIFECYCLE_EVENTS = frozenset(
    {
        AuditEventType.TRANSACTION_CREATED,
        AuditEventType.TRANSACTION_STARTED,
        AuditEventType.PAYMENT_INITIATED,
        AuditEventType.ORDER_CREATED,
        AuditEventType.PAYMENT_SUCCESS,
        AuditEventType.PAYMENT_FAILED,
        AuditEventType.PAYMENT_TIMEOUT,
        AuditEventType.TRANSACTION_COMPLETED,
        AuditEventType.TRANSACTION_FAILED,
        AuditEventType.RETRY_STARTED,
        AuditEventType.RETRY_COMPLETED,
        AuditEventType.RECOVERY_STARTED,
        AuditEventType.RECOVERY_COMPLETED,
    }
)

_FAILURE_EVENTS = frozenset(
    {
        AuditEventType.TOOL_FAILURE,
        AuditEventType.PAYMENT_FAILED,
        AuditEventType.PAYMENT_TIMEOUT,
        AuditEventType.TRANSACTION_FAILED,
    }
)

# Service attribution for the "failures by service" / audit-activity
# breakdowns, keyed by (component, event_type). `component` is the
# authoritative signal - MerchantAgent, Executor, and TransactionOrchestrator
# all reuse the same generic AuditEventType vocabulary (TRANSACTION_FAILED,
# REQUEST_RECEIVED, RETRY_STARTED, etc.) for their own, different-layer
# lifecycles (see app/agent/merchant_agent.py's `_audit` docstring: it
# explicitly records request/transaction-level events that sit *above* any
# single tool call, using the same AuditEventType.TRANSACTION_FAILED a
# checkout failure would use). Keying off event_type alone - as an earlier
# version of this file did - mislabels every agent-level failure (e.g. the
# Java Tool Layer being unreachable during tool discovery, which fails
# before a checkout transaction ever starts) as "transaction_orchestrator",
# which is actively misleading for on-call triage.
_COMPONENT_TO_SERVICE: dict[str, str] = {
    "MerchantAgent": "merchant_agent",
    "TransactionOrchestrator": "transaction_orchestrator",
    # Executor runs the agent's tool-calling loop, not the Gateway's HTTP
    # layer - there is no dedicated "Executor" entry in the dashboard's
    # fixed service list (see monitoring/health.py), so its events are
    # attributed to Merchant Agent, refined below for retry/recovery.
    "Executor": "merchant_agent",
}

# Within a component, some event types belong to a more specific
# sub-service regardless of which component recorded them.
_PAYMENT_EVENT_TYPES = frozenset(
    {
        AuditEventType.PAYMENT_FAILED,
        AuditEventType.PAYMENT_TIMEOUT,
        AuditEventType.PAYMENT_SUCCESS,
        AuditEventType.PAYMENT_INITIATED,
    }
)
_RETRY_RECOVERY_EVENT_TYPES = frozenset(
    {
        AuditEventType.RETRY_STARTED,
        AuditEventType.RETRY_COMPLETED,
        AuditEventType.RECOVERY_STARTED,
        AuditEventType.RECOVERY_COMPLETED,
    }
)
_TERMINAL_SUCCESS = {AuditEventType.TRANSACTION_COMPLETED}
_TERMINAL_FAILURE = {AuditEventType.TRANSACTION_FAILED}

_DEFAULT_SERVICE = "merchant_agent"


def _service_for(component: str, event_type: AuditEventType) -> str:
    if event_type in _PAYMENT_EVENT_TYPES:
        return "payment_service"
    if event_type in _RETRY_RECOVERY_EVENT_TYPES:
        return "failure_handling"
    # Any other event type (including TOOL_CALL/TOOL_SUCCESS/TOOL_FAILURE,
    # and the generic REQUEST_RECEIVED/TRANSACTION_*/ORDER_CREATED types
    # reused across layers) is attributed by who actually recorded it.
    return _COMPONENT_TO_SERVICE.get(component, _DEFAULT_SERVICE)


@dataclass
class _TxMeta:
    """Timestamps this class derives purely from the AuditEvent timeline -
    TransactionRecord (transaction_store.py) carries the authoritative
    session_id/transaction_type/amount/currency/state directly now, so this
    only tracks what the event stream alone can tell us: when things
    happened, and how many retries occurred."""

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_status: str = "PENDING"
    retry_count: int = 0


def _bucket_start(ts: datetime, bucket_seconds: int = BUCKET_SECONDS) -> datetime:
    epoch = int(ts.timestamp())
    floored = epoch - (epoch % bucket_seconds)
    return datetime.fromtimestamp(floored, tz=timezone.utc)


class MonitoringStore:
    """In-memory read model for the whole monitoring surface.

    Fed exclusively by:
      1. AuditEvents (via AuditService.add_listener - see wiring.py), for
         everything time-ordered: failures, retries, recovery, audit
         activity, payment/failure timelines.
      2. A periodic poll of TransactionOrchestrator.list_transactions(),
         for the authoritative current state/amount/currency of each
         transaction.

    It never re-implements transaction, payment, retry, or audit *logic* -
    only reshapes what already happened into dashboard-shaped views. All
    public methods are safe to call from any thread; the FastAPI routes
    call them synchronously (they're cheap, in-memory reads).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tx_meta: dict[str, _TxMeta] = {}
        self._latest_records: dict[str, TransactionRecord] = {}
        self._audit_log: deque[AuditEvent] = deque(maxlen=MAX_RECENT_ITEMS)
        self._failures: deque[FailureRecord] = deque(maxlen=MAX_RECENT_ITEMS)
        self._alerts: dict[str, Alert] = {}

        self._payment_buckets: dict[datetime, dict[str, int]] = {}
        self._failure_buckets: dict[datetime, int] = {}
        self._latency_buckets: dict[datetime, dict[str, Any]] = {}

        self._payment_attempts = 0
        self._successful_payments = 0
        self._failed_payments = 0
        self._payment_timeouts = 0
        self._payment_latencies_ms: deque[float] = deque(maxlen=200)
        self._transaction_durations_ms: deque[float] = deque(maxlen=200)
        self._request_timestamps: deque[float] = deque(maxlen=1000)
        self._api_latencies_ms: deque[float] = deque(maxlen=200)
        self._database_latencies_ms: deque[float] = deque(maxlen=200)
        self._llm_latencies_ms: deque[float] = deque(maxlen=200)
        self._payment_initiated_at: dict[str, datetime] = {}

        # Populated by health.py callbacks (see wiring.py) so a service
        # going DOWN can raise/clear an alert without HealthRegistry
        # knowing anything about alerts.
        self._service_statuses: dict[str, ServiceStatus] = {}

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def set_transaction_records(self, records: list[TransactionRecord]) -> None:
        with self._lock:
            self._latest_records = {r.transaction_id: r for r in records}

    def record_request(self) -> None:
        """Called once per inbound HTTP request (see wiring.py middleware
        hook) purely to compute a request-rate metric - carries no other
        state and never affects business logic."""
        with self._lock:
            self._request_timestamps.append(datetime.now(timezone.utc).timestamp())

    def on_audit_event(self, event: AuditEvent) -> Optional[FailureRecord]:
        """Ingest one AuditEvent. Returns a new FailureRecord if this event
        represents a failure worth broadcasting, else None."""
        with self._lock:
            self._audit_log.append(event)

            new_failure: Optional[FailureRecord] = None
            if event.transaction_id and event.event_type in _TRANSACTION_LIFECYCLE_EVENTS:
                meta = self._tx_meta.setdefault(event.transaction_id, _TxMeta())
                if event.event_type == AuditEventType.TRANSACTION_CREATED:
                    meta.started_at = event.timestamp
                    meta.last_status = "PENDING"
                elif event.event_type in (AuditEventType.PAYMENT_INITIATED, AuditEventType.TRANSACTION_STARTED):
                    meta.last_status = "PROCESSING"
                elif event.event_type == AuditEventType.RETRY_STARTED:
                    meta.retry_count += 1
                elif event.event_type in _TERMINAL_SUCCESS:
                    meta.completed_at = event.timestamp
                    meta.last_status = "SUCCESS"
                    if meta.started_at:
                        duration = (event.timestamp - meta.started_at).total_seconds() * 1000
                        self._transaction_durations_ms.append(duration)
                elif event.event_type in _TERMINAL_FAILURE:
                    meta.completed_at = event.timestamp
                    meta.last_status = "FAILED"
                    if meta.started_at:
                        duration = (event.timestamp - meta.started_at).total_seconds() * 1000
                        self._transaction_durations_ms.append(duration)

            if event.event_type == AuditEventType.PAYMENT_INITIATED:
                self._payment_attempts += 1
                self._bump_payment_bucket(event.timestamp, "attempted")
                if event.transaction_id:
                    self._payment_initiated_at[event.transaction_id] = event.timestamp
            elif event.event_type == AuditEventType.PAYMENT_SUCCESS:
                self._successful_payments += 1
                self._bump_payment_bucket(event.timestamp, "successful")
                self._record_payment_latency(event)
            elif event.event_type == AuditEventType.PAYMENT_FAILED:
                self._failed_payments += 1
                self._bump_payment_bucket(event.timestamp, "failed")
                self._record_payment_latency(event)
            elif event.event_type == AuditEventType.PAYMENT_TIMEOUT:
                self._payment_timeouts += 1
                self._bump_payment_bucket(event.timestamp, "timed_out")
                self._record_payment_latency(event)

            if event.event_type in _FAILURE_EVENTS:
                self._bump_failure_bucket(event.timestamp)
                new_failure = self._build_failure_record(event)
                self._failures.append(new_failure)

            return new_failure

    def _record_payment_latency(self, event: AuditEvent) -> None:
        if not event.transaction_id:
            return
        started = self._payment_initiated_at.pop(event.transaction_id, None)
        if started is not None:
            self._payment_latencies_ms.append((event.timestamp - started).total_seconds() * 1000)

    def record_api_latency(self, duration_ms: float) -> None:
        with self._lock:
            self._api_latencies_ms.append(duration_ms)
            bucket = _bucket_start(datetime.now(timezone.utc))
            row = self._latency_buckets.setdefault(
                bucket, {"api": [], "request_count": 0}
            )
            row["api"].append(duration_ms)
            row["request_count"] += 1
            self._trim_buckets(self._latency_buckets)

    def record_database_latency(self, duration_ms: float) -> None:
        with self._lock:
            self._database_latencies_ms.append(duration_ms)

    def record_llm_latency(self, duration_ms: float) -> None:
        """Fed by monitoring/llm_instrumentation.py's TimingLLMClient
        wrapper (see main.py) - one generate() call, successful or not."""
        with self._lock:
            self._llm_latencies_ms.append(duration_ms)

    def _bump_payment_bucket(self, ts: datetime, key: str) -> None:
        bucket = _bucket_start(ts)
        row = self._payment_buckets.setdefault(
            bucket, {"successful": 0, "failed": 0, "timed_out": 0, "attempted": 0}
        )
        row[key] += 1
        self._trim_buckets(self._payment_buckets)

    def _bump_failure_bucket(self, ts: datetime) -> None:
        bucket = _bucket_start(ts)
        self._failure_buckets[bucket] = self._failure_buckets.get(bucket, 0) + 1
        self._trim_buckets(self._failure_buckets)

    def _trim_buckets(self, buckets: dict) -> None:
        if len(buckets) > MAX_BUCKETS:
            for key in sorted(buckets.keys())[: len(buckets) - MAX_BUCKETS]:
                del buckets[key]

    def _build_failure_record(self, event: AuditEvent) -> FailureRecord:
        meta = self._tx_meta.get(event.transaction_id) if event.transaction_id else None
        recovery_status = "UNKNOWN"
        if event.event_type == AuditEventType.PAYMENT_TIMEOUT:
            recovery_status = "RECOVERY_PENDING"
        elif event.event_type in (AuditEventType.PAYMENT_FAILED, AuditEventType.TRANSACTION_FAILED):
            recovery_status = "UNRECOVERABLE"
        return FailureRecord(
            failure_id=f"fail-{uuid.uuid4()}",
            transaction_id=event.transaction_id,
            service=_service_for(event.component, event.event_type),
            error_type=event.error_code or event.event_type.value,
            error_message=event.error_message,
            retry_count=meta.retry_count if meta else 0,
            recovery_status=recovery_status,
            timestamp=event.timestamp,
        )

    def note_recovery_outcome(self, event: AuditEvent) -> None:
        """RECOVERY_COMPLETED doesn't itself create a new failure row, but
        it does update the recovery_status of the most recent failure for
        that transaction (best-effort, in place)."""
        if not event.transaction_id:
            return
        with self._lock:
            for record in reversed(self._failures):
                if record.transaction_id == event.transaction_id:
                    record.recovery_status = "RECOVERED" if event.status == "SUCCESS" else "UNRECOVERABLE"
                    break

    def update_service_status(self, service: str, status: ServiceStatus) -> None:
        with self._lock:
            self._service_statuses[service] = status

    # ------------------------------------------------------------------
    # Read models
    # ------------------------------------------------------------------

    def overview(self, overall_service_status: ServiceStatus) -> SystemOverview:
        with self._lock:
            statuses = [m.last_status for m in self._tx_meta.values()]
            total = len(statuses)
            successful = statuses.count("SUCCESS")
            failed = statuses.count("FAILED")
            pending = statuses.count("PENDING")
            active = statuses.count("PROCESSING")
            success_rate = (successful / total * 100.0) if total else 0.0
            avg_duration = statistics.fmean(self._transaction_durations_ms) if self._transaction_durations_ms else None
            return SystemOverview(
                system_status=overall_service_status,
                total_transactions=total,
                successful_transactions=successful,
                failed_transactions=failed,
                pending_transactions=pending,
                active_transactions=active,
                success_rate=round(success_rate, 2),
                avg_transaction_duration_ms=round(avg_duration, 1) if avg_duration is not None else None,
            )

    def payment_metrics(self) -> PaymentMetrics:
        with self._lock:
            success_rate = (
                (self._successful_payments / self._payment_attempts * 100.0) if self._payment_attempts else 0.0
            )
            avg_latency = statistics.fmean(self._payment_latencies_ms) if self._payment_latencies_ms else None
            timeline = [
                PaymentTimelineBucket(
                    bucket_start=bucket,
                    successful=row.get("successful", 0),
                    failed=row.get("failed", 0),
                    timed_out=row.get("timed_out", 0),
                )
                for bucket, row in sorted(self._payment_buckets.items())
            ]
            return PaymentMetrics(
                payment_attempts=self._payment_attempts,
                successful_payments=self._successful_payments,
                failed_payments=self._failed_payments,
                payment_timeouts=self._payment_timeouts,
                payment_success_rate=round(success_rate, 2),
                avg_payment_latency_ms=round(avg_latency, 1) if avg_latency is not None else None,
                timeline=timeline,
            )

    def failure_summary(self) -> FailureSummary:
        with self._lock:
            by_service: dict[str, int] = {}
            for record in self._failures:
                by_service[record.service] = by_service.get(record.service, 0) + 1
            retry_count = sum(m.retry_count for m in self._tx_meta.values())
            recovered = sum(1 for r in self._failures if r.recovery_status == "RECOVERED")
            unrecoverable = sum(1 for r in self._failures if r.recovery_status == "UNRECOVERABLE")
            retry_success_rate = (recovered / retry_count * 100.0) if retry_count else None
            trend = [
                FailureTrendBucket(bucket_start=bucket, count=count)
                for bucket, count in sorted(self._failure_buckets.items())
            ]
            return FailureSummary(
                total_failures=len(self._failures),
                failures_by_service=by_service,
                retry_count=retry_count,
                retry_success_rate=round(retry_success_rate, 2) if retry_success_rate is not None else None,
                unrecoverable_failures=unrecoverable,
                trend=trend,
            )

    def recent_failures(self, limit: int = 50) -> list[FailureRecord]:
        with self._lock:
            return list(self._failures)[-limit:][::-1]

    def transactions(self, limit: int = 100) -> list[TransactionSnapshot]:
        with self._lock:
            records = list(self._latest_records.values())
            snapshots: list[TransactionSnapshot] = []
            for record in records:
                meta = self._tx_meta.get(record.transaction_id, _TxMeta())
                duration_ms = None
                if meta.started_at and meta.completed_at:
                    duration_ms = (meta.completed_at - meta.started_at).total_seconds() * 1000
                snapshots.append(
                    TransactionSnapshot(
                        transaction_id=record.transaction_id,
                        session_id=record.session_id or record.request_id,
                        transaction_type=record.transaction_type,
                        state=record.state.value,
                        status=meta.last_status,
                        amount=record.amount,
                        currency=record.currency,
                        started_at=meta.started_at,
                        completed_at=meta.completed_at,
                        duration_ms=round(duration_ms, 1) if duration_ms is not None else None,
                    )
                )
            snapshots.sort(key=lambda s: s.started_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            return snapshots[:limit]

    def audit_activity(self, limit: int = 100) -> list[AuditActivityItem]:
        """Recent, sanitized audit activity. AuditEvent never carries card
        numbers/credentials in this codebase (see audit_event.py - only
        request/transaction ids, status, and error metadata), so no
        additional masking is needed here beyond not forwarding the raw
        `metadata` dict, which is intentionally omitted below."""
        with self._lock:
            events = list(self._audit_log)[-limit:][::-1]
            return [
                AuditActivityItem(
                    timestamp=e.timestamp,
                    event_type=e.event_type.value,
                    transaction_id=e.transaction_id,
                    service=_service_for(e.component, e.event_type),
                    status=e.status,
                )
                for e in events
            ]

    def performance_metrics(self) -> PerformanceMetrics:
        with self._lock:
            avg_api = statistics.fmean(self._api_latencies_ms) if self._api_latencies_ms else None
            avg_txn = statistics.fmean(self._transaction_durations_ms) if self._transaction_durations_ms else None
            avg_payment = statistics.fmean(self._payment_latencies_ms) if self._payment_latencies_ms else None
            avg_db = statistics.fmean(self._database_latencies_ms) if self._database_latencies_ms else None
            avg_llm = statistics.fmean(self._llm_latencies_ms) if self._llm_latencies_ms else None
            timeline = [
                LatencyTimelineBucket(
                    bucket_start=bucket,
                    api_latency_ms=round(statistics.fmean(row["api"]), 1) if row["api"] else None,
                    request_count=row["request_count"],
                )
                for bucket, row in sorted(self._latency_buckets.items())
            ]
            return PerformanceMetrics(
                api_latency_ms=round(avg_api, 1) if avg_api is not None else None,
                transaction_latency_ms=round(avg_txn, 1) if avg_txn is not None else None,
                payment_latency_ms=round(avg_payment, 1) if avg_payment is not None else None,
                database_latency_ms=round(avg_db, 1) if avg_db is not None else None,
                llm_latency_ms=round(avg_llm, 1) if avg_llm is not None else None,
                request_rate_per_min=self.request_rate_per_min(),
                latency_timeline=timeline,
            )

    def request_rate_per_min(self) -> float:
        with self._lock:
            cutoff = datetime.now(timezone.utc).timestamp() - 60
            recent = [t for t in self._request_timestamps if t >= cutoff]
            return float(len(recent))

    def alerts(self) -> list[Alert]:
        with self._lock:
            return sorted(self._alerts.values(), key=lambda a: a.timestamp, reverse=True)

    def raise_alert(self, key: str, severity: AlertSeverity, title: str, description: str, service: str) -> Alert:
        """Create or refresh an ACTIVE alert for `key`. Re-raising the same
        key (e.g. the same rule firing again) reuses the existing
        alert_id and status - alerts are only ever a fixed, small set of
        rules (see wiring.py), so `key` is a rule identifier, not a
        per-occurrence id."""
        with self._lock:
            existing = self._alerts.get(key)
            alert_id = existing.alert_id if existing else f"alert-{uuid.uuid4()}"
            alert = Alert(
                alert_id=alert_id,
                severity=severity,
                title=title,
                description=description,
                affected_service=service,
                timestamp=datetime.now(timezone.utc),
                status=AlertStatus.ACTIVE,
            )
            self._alerts[key] = alert
            return alert

    def resolve_alert(self, key: str) -> Optional[Alert]:
        with self._lock:
            existing = self._alerts.get(key)
            if existing is None or existing.status == AlertStatus.RESOLVED:
                return None
            resolved = existing.model_copy(update={"status": AlertStatus.RESOLVED, "timestamp": datetime.now(timezone.utc)})
            self._alerts[key] = resolved
            return resolved
