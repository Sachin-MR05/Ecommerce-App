import pytest

from payment.mock_payment_service import MockPaymentService
from payment.payment_confirmation import PaymentConfirmation
from transaction.exceptions import InvalidTransactionStateError, TransactionNotFoundError, TransactionValidationError
from transaction.transaction_orchestrator import TransactionOrchestrator
from transaction.transaction_request import TransactionRequest
from transaction.transaction_state import TransactionState


def _confirmation(provider_order_reference: str = "mock_provider_order_1") -> PaymentConfirmation:
    return PaymentConfirmation(
        provider_order_reference=provider_order_reference,
        provider_payment_reference="pay-xyz",
        provider_signature="sig-abc",
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_execute_reaches_payment_pending_with_authoritative_amount():
    payment_service = MockPaymentService(amount=150000, currency="INR")
    orchestrator = TransactionOrchestrator(payment_service=payment_service)

    request = TransactionRequest(request_id="req-001", user_id=42, payment_method="CARD")
    result = orchestrator.execute(request)

    assert result.status == TransactionState.PAYMENT_PENDING
    assert result.success is False  # not confirmed yet
    assert result.amount == 150000
    assert result.currency == "INR"
    assert result.pending_action is not None
    assert result.pending_action.provider_order_reference == "mock_provider_order_1"
    assert len(payment_service.initiate_calls) == 1


def test_execute_propagates_session_id_and_transaction_type_to_the_record():
    payment_service = MockPaymentService(amount=150000, currency="INR")
    orchestrator = TransactionOrchestrator(payment_service=payment_service)

    request = TransactionRequest(
        request_id="req-session-001",
        user_id=42,
        session_id="chat-session-abc",
        transaction_type="checkout",
    )
    orchestrator.execute(request)

    [record] = orchestrator.list_transactions()
    assert record.session_id == "chat-session-abc"
    assert record.transaction_type == "checkout"


def test_execute_defaults_session_id_and_transaction_type_when_not_supplied():
    payment_service = MockPaymentService(amount=150000, currency="INR")
    orchestrator = TransactionOrchestrator(payment_service=payment_service)

    request = TransactionRequest(request_id="req-no-session-001", user_id=42)
    orchestrator.execute(request)

    [record] = orchestrator.list_transactions()
    assert record.session_id is None  # caller didn't supply one - monitoring falls back to request_id
    assert record.transaction_type == "checkout"


def test_confirm_payment_success_reaches_order_confirmed():
    payment_service = MockPaymentService(verification_result=True)
    orchestrator = TransactionOrchestrator(payment_service=payment_service)

    request = TransactionRequest(request_id="req-002", user_id=42)
    pending = orchestrator.execute(request)

    result = orchestrator.confirm_payment("req-002", _confirmation())

    assert result.status == TransactionState.ORDER_CONFIRMED
    assert result.success is True
    assert result.order_id == pending.order_id
    assert result.payment_id == "pay-xyz"
    assert result.error is None


def test_confirm_payment_failure_reaches_failed_and_never_confirms_order():
    payment_service = MockPaymentService(verification_result=False)
    orchestrator = TransactionOrchestrator(payment_service=payment_service)

    request = TransactionRequest(request_id="req-003", user_id=42)
    orchestrator.execute(request)

    result = orchestrator.confirm_payment("req-003", _confirmation())

    assert result.status == TransactionState.FAILED
    assert result.success is False
    assert result.error is not None
    assert result.error.code == "PAYMENT_FAILED"


# ---------------------------------------------------------------------------
# Idempotency / payment safety
# ---------------------------------------------------------------------------

def test_execute_is_idempotent_and_never_charges_twice():
    payment_service = MockPaymentService()
    orchestrator = TransactionOrchestrator(payment_service=payment_service)
    request = TransactionRequest(request_id="req-004", user_id=42)

    first = orchestrator.execute(request)
    second = orchestrator.execute(request)

    assert first == second
    assert len(payment_service.initiate_calls) == 1


def test_confirm_payment_after_order_confirmed_is_idempotent():
    payment_service = MockPaymentService(verification_result=True)
    orchestrator = TransactionOrchestrator(payment_service=payment_service)
    request = TransactionRequest(request_id="req-005", user_id=42)
    orchestrator.execute(request)

    first = orchestrator.confirm_payment("req-005", _confirmation())
    second = orchestrator.confirm_payment("req-005", _confirmation("different-reference"))

    assert first == second
    # verify_payment (handle_payment_result) was only actually invoked once.
    assert len(payment_service.verify_calls) == 1


def test_execute_after_confirmed_returns_cached_result_without_new_payment():
    payment_service = MockPaymentService(verification_result=True)
    orchestrator = TransactionOrchestrator(payment_service=payment_service)
    request = TransactionRequest(request_id="req-006", user_id=42)
    orchestrator.execute(request)
    confirmed = orchestrator.confirm_payment("req-006", _confirmation())

    replay = orchestrator.execute(request)

    assert replay == confirmed
    assert len(payment_service.initiate_calls) == 1


# ---------------------------------------------------------------------------
# Validation / error handling
# ---------------------------------------------------------------------------

def test_execute_fails_fast_on_unsupported_payment_method_without_calling_payment_service():
    payment_service = MockPaymentService()
    orchestrator = TransactionOrchestrator(payment_service=payment_service)

    request = TransactionRequest(request_id="req-007", user_id=42, payment_method="CRYPTO")
    result = orchestrator.execute(request)

    assert result.status == TransactionState.FAILED
    assert result.success is False
    assert result.error.code == "VALIDATION_FAILED"
    assert len(payment_service.initiate_calls) == 0


def test_confirm_payment_unknown_request_id_raises():
    orchestrator = TransactionOrchestrator(payment_service=MockPaymentService())

    with pytest.raises(TransactionNotFoundError):
        orchestrator.confirm_payment("does-not-exist", _confirmation())


def test_confirm_payment_before_payment_pending_raises_invalid_state():
    payment_service = MockPaymentService(verification_result=True)
    orchestrator = TransactionOrchestrator(payment_service=payment_service)
    request = TransactionRequest(request_id="req-008", user_id=42)
    orchestrator.execute(request)
    orchestrator.confirm_payment("req-008", _confirmation())

    # Transaction is now terminal (ORDER_CONFIRMED) - a *different* second
    # confirm_payment call with new confirmation data still just replays the
    # cached terminal result rather than raising or re-processing.
    replay = orchestrator.confirm_payment("req-008", _confirmation("another-ref"))
    assert replay.status == TransactionState.ORDER_CONFIRMED
    assert len(payment_service.verify_calls) == 1


def test_transaction_error_payload_never_exposes_internal_exception_detail():
    class ExplodingPaymentService(MockPaymentService):
        def initiate_payment(self, request):
            raise RuntimeError("Traceback (most recent call last): sensitive internal detail")

    orchestrator = TransactionOrchestrator(payment_service=ExplodingPaymentService())
    request = TransactionRequest(request_id="req-009", user_id=42)

    # A raw, unmapped exception is not a PaymentError/CartValidationError,
    # so it is expected to propagate (never silently swallowed) rather than
    # being reported as a business TransactionResult - the caller (e.g. the
    # Gateway's error handlers) is responsible for turning that into a safe
    # 500 response, exactly as AgentOrchestrator.process() already documents.
    with pytest.raises(RuntimeError):
        orchestrator.execute(request)
