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


def test_merchant_agent_level_failures_are_not_misattributed_to_transaction_orchestrator():
    """Regression test: MerchantAgent records its own request-lifecycle
    failures (e.g. the Java Tool Layer being unreachable during tool
    discovery, which fails before any checkout transaction exists) using
    component="MerchantAgent" and the *same* generic AuditEventType values
    (REQUEST_RECEIVED, TRANSACTION_FAILED) that TransactionOrchestrator
    uses for real checkout failures. Service attribution must key off
    `component`, not just `event_type`, or every agent-side outage shows up
    mislabeled as a checkout/transaction-orchestrator problem on the
    dashboard - found by live-testing the actual /agent/message endpoint
    with the Java Tool Layer down."""
    store = MonitoringStore()

    event = AuditEvent.new(
        request_id="req-agent-1",
        event_type=AuditEventType.TRANSACTION_FAILED,
        component="MerchantAgent",
        operation="agent_run",
        status="FAILED",
        transaction_id=None,
        error_message="Could not reach tool service: Connection refused",
    )
    failure = store.on_audit_event(event)

    assert failure is not None
    assert failure.service == "merchant_agent"

    activity = store.audit_activity(limit=10)
    assert activity[0].service == "merchant_agent"

    summary = store.failure_summary()
    assert summary.failures_by_service == {"merchant_agent": 1}
    assert "transaction_orchestrator" not in summary.failures_by_service


def test_checkout_payment_failure_still_attributes_to_payment_service_regardless_of_component():
    store = MonitoringStore()
    event = AuditEvent.new(
        request_id="req-checkout-1",
        event_type=AuditEventType.PAYMENT_FAILED,
        component="TransactionOrchestrator",
        operation="confirm_payment",
        status="FAILED",
        transaction_id="txn-1",
    )
    failure = store.on_audit_event(event)
    assert failure.service == "payment_service"
