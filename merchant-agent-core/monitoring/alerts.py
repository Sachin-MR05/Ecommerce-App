from __future__ import annotations

from typing import Optional

from monitoring.models import Alert, AlertSeverity, ServiceStatus
from monitoring.store import MonitoringStore

# Fixed, documented thresholds. These are deliberately simple (rolling
# totals, not sliding windows) - good enough for a dev/staging monitoring
# view. Tune or replace with a real rules engine before relying on this
# for production paging.
FAILURE_RATE_WARNING = 0.30
FAILURE_RATE_CRITICAL = 0.60
MIN_TRANSACTIONS_FOR_RATE_ALERT = 5

TIMEOUT_RATE_WARNING = 0.20
MIN_PAYMENT_ATTEMPTS_FOR_TIMEOUT_ALERT = 5

EXCESSIVE_RETRY_THRESHOLD = 3

API_LATENCY_WARNING_MS = 2000.0


def evaluate_alerts(store: MonitoringStore, overall_status: ServiceStatus) -> list[tuple[str, Alert]]:
    """Recompute every threshold rule and raise/resolve alerts as needed.

    Returns (key, alert) pairs for anything that changed this pass, so the
    caller (wiring.py) can decide what to broadcast over the WebSocket -
    this function itself never touches the event bus.
    """
    changed: list[tuple[str, Alert]] = []

    overview = store.overview(overall_status)
    if overview.total_transactions >= MIN_TRANSACTIONS_FOR_RATE_ALERT and overview.total_transactions > 0:
        failure_rate = overview.failed_transactions / overview.total_transactions
        key = "transaction_failure_rate"
        if failure_rate >= FAILURE_RATE_CRITICAL:
            changed.append((key, store.raise_alert(
                key, AlertSeverity.CRITICAL, "Transaction failure rate exceeded threshold",
                f"{failure_rate:.0%} of transactions have failed (critical threshold {FAILURE_RATE_CRITICAL:.0%}).",
                "transaction_orchestrator",
            )))
        elif failure_rate >= FAILURE_RATE_WARNING:
            changed.append((key, store.raise_alert(
                key, AlertSeverity.WARNING, "Transaction failure rate exceeded threshold",
                f"{failure_rate:.0%} of transactions have failed (warning threshold {FAILURE_RATE_WARNING:.0%}).",
                "transaction_orchestrator",
            )))
        else:
            resolved = store.resolve_alert(key)
            if resolved:
                changed.append((key, resolved))

    payments = store.payment_metrics()
    if payments.payment_attempts >= MIN_PAYMENT_ATTEMPTS_FOR_TIMEOUT_ALERT:
        timeout_rate = payments.payment_timeouts / payments.payment_attempts
        key = "payment_timeout_rate"
        if timeout_rate >= TIMEOUT_RATE_WARNING:
            changed.append((key, store.raise_alert(
                key, AlertSeverity.WARNING, "Payment timeout rate exceeded threshold",
                f"{timeout_rate:.0%} of payment attempts have timed out (threshold {TIMEOUT_RATE_WARNING:.0%}).",
                "payment_service",
            )))
        else:
            resolved = store.resolve_alert(key)
            if resolved:
                changed.append((key, resolved))

    failures = store.failure_summary()
    key = "excessive_retries"
    if failures.retry_count >= EXCESSIVE_RETRY_THRESHOLD:
        changed.append((key, store.raise_alert(
            key, AlertSeverity.WARNING, "Excessive retries detected",
            f"{failures.retry_count} retries recorded across active transactions.",
            "failure_handling",
        )))
    else:
        resolved = store.resolve_alert(key)
        if resolved:
            changed.append((key, resolved))

    performance = store.performance_metrics()
    key = "api_latency_high"
    if performance.api_latency_ms is not None and performance.api_latency_ms >= API_LATENCY_WARNING_MS:
        changed.append((key, store.raise_alert(
            key, AlertSeverity.WARNING, "Service latency exceeded threshold",
            f"Average API latency is {performance.api_latency_ms:.0f}ms (threshold {API_LATENCY_WARNING_MS:.0f}ms).",
            "agent_gateway",
        )))
    else:
        resolved = store.resolve_alert(key)
        if resolved:
            changed.append((key, resolved))

    return changed


def evaluate_service_health_alert(store: MonitoringStore, service: str, status: ServiceStatus) -> Optional[tuple[str, Alert]]:
    key = f"service_down:{service}"
    if status == ServiceStatus.DOWN:
        return key, store.raise_alert(
            key, AlertSeverity.CRITICAL, f"{service.replace('_', ' ').title()} unavailable",
            f"No heartbeat received from {service.replace('_', ' ')}.",
            service,
        )
    resolved = store.resolve_alert(key)
    if resolved:
        return key, resolved
    return None
