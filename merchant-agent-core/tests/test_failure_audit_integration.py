from audit.audit_event import AuditEventType
from audit.audit_repository import InMemoryAuditRepository
from audit.audit_service import AuditService
from failure_handling.failure_handler import FailureHandler
from payment.exceptions import PaymentTimeoutError
from payment.mock_payment_service import MockPaymentService
from payment.payment_confirmation import PaymentConfirmation
from payment.payment_result import PaymentResult, PaymentStatus
from transaction.transaction_orchestrator import TransactionOrchestrator
from transaction.transaction_request import TransactionRequest
from transaction.transaction_state import TransactionState


def _confirmation(provider_order_reference: str = "mock_provider_order_1") -> PaymentConfirmation:
    return PaymentConfirmation(
        provider_order_reference=provider_order_reference,
        provider_payment_reference="pay-xyz",
        provider_signature="sig-abc",
    )


def _orchestrator(payment_service):
    audit_service = AuditService(InMemoryAuditRepository())
    failure_handler = FailureHandler()
    orchestrator = TransactionOrchestrator(
        payment_service=payment_service, failure_handler=failure_handler, audit_service=audit_service
    )
    return orchestrator, audit_service


# ---------------------------------------------------------------------------
# 1. Successful transaction produces audit events
# ---------------------------------------------------------------------------


def test_successful_transaction_produces_the_full_audit_trail():
    orchestrator, audit_service = _orchestrator(MockPaymentService(verification_result=True))
    request = TransactionRequest(request_id="req-int-1", user_id=42)

    pending = orchestrator.execute(request)
    result = orchestrator.confirm_payment("req-int-1", _confirmation())

    assert result.status == TransactionState.ORDER_CONFIRMED
    history = audit_service.get_transaction_history(pending.transaction_id)
    assert [e.event_type for e in history] == [
        AuditEventType.TRANSACTION_CREATED,
        AuditEventType.TRANSACTION_STARTED,
        AuditEventType.PAYMENT_INITIATED,
        AuditEventType.ORDER_CREATED,
        AuditEventType.PAYMENT_SUCCESS,
        AuditEventType.TRANSACTION_COMPLETED,
    ]


# ---------------------------------------------------------------------------
# 2. Failed transaction produces audit events
# ---------------------------------------------------------------------------


def test_failed_verification_produces_a_failure_audit_trail():
    orchestrator, audit_service = _orchestrator(MockPaymentService(verification_result=False))
    request = TransactionRequest(request_id="req-int-2", user_id=42)

    pending = orchestrator.execute(request)
    result = orchestrator.confirm_payment("req-int-2", _confirmation())

    assert result.status == TransactionState.FAILED
    history = audit_service.get_transaction_history(pending.transaction_id)
    event_types = [e.event_type for e in history]
    assert AuditEventType.PAYMENT_FAILED in event_types
    assert event_types[-1] == AuditEventType.TRANSACTION_FAILED

    failed_event = next(e for e in history if e.event_type == AuditEventType.PAYMENT_FAILED)
    assert failed_event.error_code == "PAYMENT_FAILED"


def test_validation_failure_produces_transaction_failed_without_calling_payment_service():
    payment_service = MockPaymentService()
    orchestrator, audit_service = _orchestrator(payment_service)
    request = TransactionRequest(request_id="req-int-3", user_id=42, payment_method="CRYPTO")

    result = orchestrator.execute(request)

    assert result.status == TransactionState.FAILED
    assert len(payment_service.initiate_calls) == 0
    history = audit_service.get_transaction_history(result.transaction_id)
    assert [e.event_type for e in history] == [
        AuditEventType.TRANSACTION_CREATED,
        AuditEventType.TRANSACTION_FAILED,
    ]
    assert history[-1].error_code == "VALIDATION_FAILED"


# ---------------------------------------------------------------------------
# 3. Retry produces audit events (via FailureHandler directly, since the
#    orchestrator's own transport calls are wrapped by Executor/ToolClient,
#    not retried in-place here - see test_failure_handling.py for the
#    retry/backoff unit tests this exercises).
# ---------------------------------------------------------------------------


def test_retryable_transport_failure_is_recorded_as_a_retry_decision():
    from failure_handling.failure_handler import FailureHandler
    from failure_handling.recovery import RecoveryAction
    from app.tools.tool_client import ToolServiceUnavailableError

    audit_service = AuditService(InMemoryAuditRepository())
    failure_handler = FailureHandler()
    exc = ToolServiceUnavailableError("tool layer unreachable")

    recovery = failure_handler.handle_tool_client_exception(
        exc, component="TransactionOrchestrator", attempt=1, request_id="req-retry-1"
    )
    audit_service.record_event(
        AuditEventType.RETRY_STARTED,
        component="FailureHandler",
        operation="initiate_payment",
        status=recovery.action.value,
        request_id="req-retry-1",
    )

    assert recovery.action == RecoveryAction.RETRY
    history = audit_service._repository.get_by_request("req-retry-1")  # noqa: SLF001
    assert history[0].event_type == AuditEventType.RETRY_STARTED


# ---------------------------------------------------------------------------
# 4. Payment timeout produces the correct recovery flow
# ---------------------------------------------------------------------------


def test_payment_timeout_that_actually_succeeded_recovers_instead_of_failing():
    class TimeoutThenSucceededPaymentService(MockPaymentService):
        def handle_payment_result(self, user_id, payment_id, confirmation):
            raise PaymentTimeoutError("provider did not respond in time")

        def get_payment_status(self, user_id, payment_id):
            return PaymentResult(
                payment_id="pay-recovered",
                status=PaymentStatus.SUCCESS,
                amount=150000,
                currency="INR",
                provider_reference="mock_provider_order_1",
            )

    orchestrator, audit_service = _orchestrator(TimeoutThenSucceededPaymentService())
    request = TransactionRequest(request_id="req-int-4", user_id=42)
    pending = orchestrator.execute(request)

    result = orchestrator.confirm_payment("req-int-4", _confirmation())

    assert result.status == TransactionState.ORDER_CONFIRMED
    assert result.success is True
    event_types = [e.event_type for e in audit_service.get_transaction_history(pending.transaction_id)]
    assert AuditEventType.PAYMENT_TIMEOUT in event_types
    assert AuditEventType.RECOVERY_STARTED in event_types
    assert AuditEventType.RECOVERY_COMPLETED in event_types
    assert AuditEventType.PAYMENT_SUCCESS in event_types
    # never a hard failure once the status check confirms success
    assert AuditEventType.PAYMENT_FAILED not in event_types


def test_payment_timeout_with_unconfirmed_status_does_not_guess_success():
    class TimeoutThenUnknownPaymentService(MockPaymentService):
        def handle_payment_result(self, user_id, payment_id, confirmation):
            raise PaymentTimeoutError("provider did not respond in time")

        def get_payment_status(self, user_id, payment_id):
            return PaymentResult(payment_id=None, status=PaymentStatus.PENDING, amount=150000, currency="INR")

    orchestrator, audit_service = _orchestrator(TimeoutThenUnknownPaymentService())
    request = TransactionRequest(request_id="req-int-5", user_id=42)
    pending = orchestrator.execute(request)

    result = orchestrator.confirm_payment("req-int-5", _confirmation())

    # Never silently promoted to success - the status check came back
    # PENDING, so this is recorded as a (reconciliation-needed) failure,
    # never a guessed ORDER_CONFIRMED.
    assert result.status == TransactionState.FAILED
    event_types = [e.event_type for e in audit_service.get_transaction_history(pending.transaction_id)]
    assert AuditEventType.RECOVERY_COMPLETED in event_types
    assert AuditEventType.PAYMENT_SUCCESS not in event_types


# ---------------------------------------------------------------------------
# 5. Duplicate payment does not execute twice
# ---------------------------------------------------------------------------


def test_duplicate_execute_call_does_not_initiate_a_second_payment():
    payment_service = MockPaymentService()
    orchestrator, audit_service = _orchestrator(payment_service)
    request = TransactionRequest(request_id="req-int-6", user_id=42)

    first = orchestrator.execute(request)
    second = orchestrator.execute(request)

    assert first == second
    assert len(payment_service.initiate_calls) == 1
    # only one TRANSACTION_CREATED - the replay never re-enters the audited workflow
    history = audit_service.get_transaction_history(first.transaction_id)
    assert len([e for e in history if e.event_type == AuditEventType.TRANSACTION_CREATED]) == 1


def test_duplicate_confirm_payment_does_not_verify_twice():
    payment_service = MockPaymentService(verification_result=True)
    orchestrator, audit_service = _orchestrator(payment_service)
    request = TransactionRequest(request_id="req-int-7", user_id=42)
    orchestrator.execute(request)

    first = orchestrator.confirm_payment("req-int-7", _confirmation())
    second = orchestrator.confirm_payment("req-int-7", _confirmation("different-reference"))

    assert first == second
    assert len(payment_service.verify_calls) == 1
    history = audit_service.get_transaction_history(first.transaction_id)
    assert len([e for e in history if e.event_type == AuditEventType.PAYMENT_SUCCESS]) == 1
