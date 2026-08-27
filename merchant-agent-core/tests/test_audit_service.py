from audit.audit_event import AuditEvent, AuditEventType
from audit.audit_repository import InMemoryAuditRepository, JsonlAuditRepository
from audit.audit_service import AuditService


# ---------------------------------------------------------------------------
# 1. Audit event creation
# ---------------------------------------------------------------------------


def test_audit_event_creation_populates_required_fields():
    event = AuditEvent.new(
        request_id="req-1",
        event_type=AuditEventType.TOOL_CALL,
        component="Executor",
        operation="create_order",
        status="STARTED",
        transaction_id="txn-1",
    )

    assert event.event_id.startswith("evt-")
    assert event.request_id == "req-1"
    assert event.transaction_id == "txn-1"
    assert event.event_type == AuditEventType.TOOL_CALL
    assert event.component == "Executor"
    assert event.operation == "create_order"
    assert event.status == "STARTED"
    assert event.timestamp is not None
    assert event.actor == "system"
    assert event.metadata == {}


def test_audit_event_ids_are_unique_per_event():
    event_a = AuditEvent.new(
        request_id="req-1", event_type=AuditEventType.TOOL_CALL, component="Executor", operation="op", status="OK"
    )
    event_b = AuditEvent.new(
        request_id="req-1", event_type=AuditEventType.TOOL_CALL, component="Executor", operation="op", status="OK"
    )

    assert event_a.event_id != event_b.event_id


# ---------------------------------------------------------------------------
# 2. Audit event persistence
# ---------------------------------------------------------------------------


def test_audit_service_persists_events_via_in_memory_repository():
    service = AuditService(InMemoryAuditRepository())

    service.record_event(
        AuditEventType.REQUEST_RECEIVED,
        component="Gateway",
        operation="agent_run",
        status="RECEIVED",
        request_id="req-1",
    )

    history = service.get_transaction_history("does-not-matter")
    assert history == []  # no transaction_id was supplied, so it's untracked by transaction

    # but it is retrievable by request via the repository directly
    repository = service._repository  # noqa: SLF001 - test-only introspection
    assert len(repository.get_by_request("req-1")) == 1


def test_jsonl_audit_repository_appends_without_overwriting(tmp_path):
    path = tmp_path / "audit.jsonl"
    repository = JsonlAuditRepository(path)
    service = AuditService(repository)

    service.record_event(
        AuditEventType.TRANSACTION_CREATED,
        component="Executor",
        operation="create_order",
        status="STARTED",
        request_id="req-1",
        transaction_id="txn-1",
    )
    service.record_event(
        AuditEventType.TRANSACTION_COMPLETED,
        component="Executor",
        operation="create_order",
        status="SUCCESS",
        request_id="req-1",
        transaction_id="txn-1",
    )

    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2  # append-only - both records preserved, none rewritten

    history = service.get_transaction_history("txn-1")
    assert [e.event_type for e in history] == [
        AuditEventType.TRANSACTION_CREATED,
        AuditEventType.TRANSACTION_COMPLETED,
    ]


# ---------------------------------------------------------------------------
# 3. Transaction history retrieval
# ---------------------------------------------------------------------------


def test_get_transaction_history_returns_only_events_for_that_transaction():
    service = AuditService(InMemoryAuditRepository())

    service.record_event(
        AuditEventType.ORDER_CREATED, component="Executor", operation="create_order",
        status="SUCCESS", request_id="req-1", transaction_id="txn-1",
    )
    service.record_event(
        AuditEventType.ORDER_CREATED, component="Executor", operation="create_order",
        status="SUCCESS", request_id="req-2", transaction_id="txn-2",
    )

    history = service.get_transaction_history("txn-1")

    assert len(history) == 1
    assert history[0].transaction_id == "txn-1"


def test_transaction_history_is_returned_in_chronological_order():
    service = AuditService(InMemoryAuditRepository())

    service.record_event(
        AuditEventType.PAYMENT_INITIATED, component="Executor", operation="verify_payment",
        status="STARTED", request_id="req-1", transaction_id="txn-1",
    )
    service.record_event(
        AuditEventType.PAYMENT_SUCCESS, component="Executor", operation="verify_payment",
        status="SUCCESS", request_id="req-1", transaction_id="txn-1",
    )

    history = service.get_transaction_history("txn-1")

    assert [e.event_type for e in history] == [AuditEventType.PAYMENT_INITIATED, AuditEventType.PAYMENT_SUCCESS]
    assert history[0].timestamp <= history[1].timestamp


# ---------------------------------------------------------------------------
# 4. Successful payment audit trail
# ---------------------------------------------------------------------------


def test_successful_payment_produces_a_complete_audit_trail():
    service = AuditService(InMemoryAuditRepository())
    txn = "txn-success"

    service.record_event(AuditEventType.REQUEST_RECEIVED, "Gateway", "agent_run", "RECEIVED", "req-1")
    service.record_event(AuditEventType.TRANSACTION_CREATED, "Executor", "create_order", "STARTED", "req-1", txn)
    service.record_event(AuditEventType.PAYMENT_INITIATED, "Executor", "verify_payment", "STARTED", "req-1", txn)
    service.record_event(AuditEventType.PAYMENT_SUCCESS, "Executor", "verify_payment", "SUCCESS", "req-1", txn)
    service.record_event(AuditEventType.ORDER_CREATED, "Executor", "create_order", "SUCCESS", "req-1", txn)
    service.record_event(AuditEventType.TRANSACTION_COMPLETED, "MerchantAgent", "agent_run", "SUCCESS", "req-1", txn)

    history = service.get_transaction_history(txn)
    event_types = [e.event_type for e in history]

    assert event_types == [
        AuditEventType.TRANSACTION_CREATED,
        AuditEventType.PAYMENT_INITIATED,
        AuditEventType.PAYMENT_SUCCESS,
        AuditEventType.ORDER_CREATED,
        AuditEventType.TRANSACTION_COMPLETED,
    ]
    assert all(e.error_code is None for e in history)


# ---------------------------------------------------------------------------
# 5. Failed payment audit trail
# ---------------------------------------------------------------------------


def test_failed_payment_produces_a_failure_audit_trail_with_error_detail():
    service = AuditService(InMemoryAuditRepository())
    txn = "txn-failed"

    service.record_event(AuditEventType.PAYMENT_INITIATED, "Executor", "verify_payment", "STARTED", "req-2", txn)
    service.record_event(
        AuditEventType.PAYMENT_FAILED, "Executor", "verify_payment", "FAILED", "req-2", txn,
        error_code="PAYMENT_DECLINED", error_message="Card declined by issuer",
    )
    service.record_event(AuditEventType.TRANSACTION_FAILED, "MerchantAgent", "agent_run", "FAILED", "req-2", txn)

    history = service.get_transaction_history(txn)

    assert history[-1].event_type == AuditEventType.TRANSACTION_FAILED
    failed_event = next(e for e in history if e.event_type == AuditEventType.PAYMENT_FAILED)
    assert failed_event.error_code == "PAYMENT_DECLINED"
    assert failed_event.error_message == "Card declined by issuer"


# ---------------------------------------------------------------------------
# 6. Retry audit events
# ---------------------------------------------------------------------------


def test_retry_lifecycle_events_are_recorded_and_traceable():
    service = AuditService(InMemoryAuditRepository())
    txn = "txn-retry"

    service.record_event(AuditEventType.RETRY_STARTED, "FailureHandler", "verify_payment", "STARTED", "req-3", txn)
    service.record_event(AuditEventType.RETRY_COMPLETED, "FailureHandler", "verify_payment", "SUCCESS", "req-3", txn)

    history = service.get_transaction_history(txn)

    assert [e.event_type for e in history] == [AuditEventType.RETRY_STARTED, AuditEventType.RETRY_COMPLETED]


# ---------------------------------------------------------------------------
# 7. Recovery audit events
# ---------------------------------------------------------------------------


def test_recovery_lifecycle_events_are_recorded_and_traceable():
    service = AuditService(InMemoryAuditRepository())
    txn = "txn-recovery"

    service.record_event(AuditEventType.PAYMENT_TIMEOUT, "Executor", "verify_payment", "TIMEOUT", "req-4", txn)
    service.record_event(AuditEventType.RECOVERY_STARTED, "FailureHandler", "verify_payment", "STARTED", "req-4", txn)
    service.record_event(AuditEventType.RECOVERY_COMPLETED, "FailureHandler", "verify_payment", "RECOVERED", "req-4", txn)

    history = service.get_transaction_history(txn)

    assert [e.event_type for e in history] == [
        AuditEventType.PAYMENT_TIMEOUT,
        AuditEventType.RECOVERY_STARTED,
        AuditEventType.RECOVERY_COMPLETED,
    ]


# ---------------------------------------------------------------------------
# 8. request_id / transaction_id traceability
# ---------------------------------------------------------------------------


def test_every_event_carries_request_id_transaction_id_and_a_unique_event_id():
    service = AuditService(InMemoryAuditRepository())

    event = service.record_event(
        AuditEventType.TOOL_CALL, component="Executor", operation="create_order",
        status="STARTED", request_id="req-5", transaction_id="txn-5",
    )

    assert event.request_id == "req-5"
    assert event.transaction_id == "txn-5"
    assert event.event_id

    history = service.get_transaction_history("txn-5")
    assert history[0].event_id == event.event_id
    assert history[0].request_id == event.request_id


def test_events_without_a_transaction_id_are_still_recorded():
    service = AuditService(InMemoryAuditRepository())

    event = service.record_event(
        AuditEventType.REQUEST_RECEIVED, component="Gateway", operation="agent_run", status="RECEIVED",
        request_id="req-6",
    )

    assert event.transaction_id is None
    assert service.get_transaction_history("txn-does-not-exist") == []
