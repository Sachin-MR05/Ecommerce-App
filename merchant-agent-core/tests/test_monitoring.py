from __future__ import annotations

from datetime import datetime, timezone

from audit.audit_event import AuditEvent, AuditEventType
from monitoring.store import MonitoringStore


def _event(event_type: AuditEventType, transaction_id: str = "txn-1", **kwargs) -> AuditEvent:
    return AuditEvent.new(
        request_id=kwargs.pop("request_id", "req-1"),
        event_type=event_type,
        component="TransactionOrchestrator",
        operation="checkout",
        status=kwargs.pop("status", "STARTED"),
        transaction_id=transaction_id,
        **kwargs,
    )


def test_transaction_lifecycle_tracked_from_audit_events():
    store = MonitoringStore()

    store.on_audit_event(_event(AuditEventType.TRANSACTION_CREATED, status="STARTED"))
    store.on_audit_event(_event(AuditEventType.PAYMENT_INITIATED, status="STARTED"))
    store.on_audit_event(_event(AuditEventType.PAYMENT_SUCCESS, status="SUCCESS"))
    store.on_audit_event(_event(AuditEventType.TRANSACTION_COMPLETED, status="SUCCESS"))

    from monitoring.models import ServiceStatus
    overview = store.overview(ServiceStatus.UP)
    assert overview.total_transactions == 1
    assert overview.successful_transactions == 1
    assert overview.failed_transactions == 0

    payments = store.payment_metrics()
    assert payments.payment_attempts == 1
    assert payments.successful_payments == 1
    assert payments.payment_success_rate == 100.0


def test_failed_payment_produces_failure_record_and_alert_after_threshold():
    store = MonitoringStore()

    for i in range(5):
        txn = f"txn-{i}"
        store.on_audit_event(_event(AuditEventType.TRANSACTION_CREATED, transaction_id=txn, request_id=f"req-{i}"))
        store.on_audit_event(_event(AuditEventType.PAYMENT_INITIATED, transaction_id=txn, request_id=f"req-{i}"))
        store.on_audit_event(
            _event(
                AuditEventType.PAYMENT_FAILED,
                transaction_id=txn,
                request_id=f"req-{i}",
                status="FAILED",
                error_code="PAYMENT_DECLINED",
                error_message="card declined",
            )
        )
        store.on_audit_event(
            _event(AuditEventType.TRANSACTION_FAILED, transaction_id=txn, request_id=f"req-{i}", status="FAILED")
        )

    failures = store.recent_failures(limit=10)
    assert len(failures) == 10  # PAYMENT_FAILED + TRANSACTION_FAILED per iteration
    assert any(f.error_message == "card declined" for f in failures)

    from monitoring.alerts import evaluate_alerts
    from monitoring.models import ServiceStatus

    changed = evaluate_alerts(store, ServiceStatus.UP)
    keys = {k for k, _ in changed}
    assert "transaction_failure_rate" in keys


def test_retry_count_tracked_per_transaction():
    store = MonitoringStore()
    store.on_audit_event(_event(AuditEventType.TRANSACTION_CREATED))
    for _ in range(3):
        store.on_audit_event(_event(AuditEventType.RETRY_STARTED, status="STARTED"))

    summary = store.failure_summary()
    assert summary.retry_count == 3
