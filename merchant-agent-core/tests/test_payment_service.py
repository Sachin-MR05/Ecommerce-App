"""Tests for PaymentService implementations.

Uses the same StubToolClient/ToolResponse pattern as
tests/test_order_tools_flow.py so no real HTTP or Java service is needed.
"""
import pytest

from contracts.tool_error import ToolError, ToolErrorType
from contracts.tool_response import ToolResponse
from payment.exceptions import PaymentInitiationError, PaymentVerificationError
from payment.mock_payment_service import MockPaymentService
from payment.payment_confirmation import PaymentConfirmation
from payment.payment_request import PaymentRequest
from payment.payment_result import PaymentStatus
from payment.payment_service import RazorpayToolPaymentService
from tools.order.order_tool_adapter import OrderToolAdapter
from tools.payment.razorpay_payment_tool_adapter import RazorpayPaymentToolAdapter


class StubToolClient:
    """Same double shape used across tests/test_*_flow.py."""

    def __init__(self, execute_results=None):
        self._execute_results = execute_results or {}
        self.executed_calls = []

    def execute_tool(self, tool_name, arguments, user_id=None, context=None, request_id=None):
        self.executed_calls.append((tool_name, arguments, user_id, request_id))
        result = self._execute_results.get(tool_name)
        assert result is not None, f"Unexpected tool call: {tool_name}"
        if isinstance(result, list):
            result = result[len([c for c in self.executed_calls if c[0] == tool_name]) - 1]
        return result


CHECKOUT_DATA = {
    "orderId": 100,
    "razorpayOrderId": "rzp_order_abc123",
    "amount": 29900,
    "currency": "INR",
    "keyId": "rzp_test_key",
}


def _ok(data):
    return ToolResponse(requestId="req-1", success=True, result=data)


def _err(code, message, error_type=ToolErrorType.TOOL_EXECUTION_ERROR):
    return ToolResponse(
        requestId="req-1",
        success=False,
        error=ToolError(code=code, message=message, type=error_type),
    )


# ---------------------------------------------------------------------------
# RazorpayToolPaymentService.initiate_payment
# ---------------------------------------------------------------------------

def test_initiate_payment_returns_authoritative_amount_from_tool_layer():
    tool_client = StubToolClient(execute_results={"create_order": _ok(CHECKOUT_DATA)})
    service = RazorpayToolPaymentService(
        RazorpayPaymentToolAdapter(tool_client), OrderToolAdapter(tool_client)
    )

    request = PaymentRequest(
        transaction_id="txn-req-001", user_id=42, payment_method="CARD", idempotency_key="req-001"
    )
    result = service.initiate_payment(request)

    assert result.status == PaymentStatus.PENDING
    assert result.amount == 29900
    assert result.currency == "INR"
    assert result.provider_reference == "rzp_order_abc123"
    assert result.metadata["order_id"] == "100"
    # create_order takes no client-supplied amount at all.
    assert tool_client.executed_calls[0] == ("create_order", {}, 42, "req-001")


def test_initiate_payment_raises_on_empty_cart():
    tool_client = StubToolClient(
        execute_results={"create_order": _err("PAYMENT_ERROR", "Your cart is empty")}
    )
    service = RazorpayToolPaymentService(
        RazorpayPaymentToolAdapter(tool_client), OrderToolAdapter(tool_client)
    )
    request = PaymentRequest(
        transaction_id="txn-req-002", user_id=42, payment_method="CARD", idempotency_key="req-002"
    )

    with pytest.raises(PaymentInitiationError):
        service.initiate_payment(request)


# ---------------------------------------------------------------------------
# RazorpayToolPaymentService.handle_payment_result
# ---------------------------------------------------------------------------

def test_handle_payment_result_success():
    tool_client = StubToolClient(
        execute_results={
            "verify_payment": _ok(
                {"verified": True, "message": "Payment verified", "order": {"id": 100, "status": "PAID", "totalAmount": 299.0}}
            )
        }
    )
    service = RazorpayToolPaymentService(
        RazorpayPaymentToolAdapter(tool_client), OrderToolAdapter(tool_client)
    )
    confirmation = PaymentConfirmation(
        provider_order_reference="rzp_order_abc123",
        provider_payment_reference="rzp_pay_xyz",
        provider_signature="sig123",
    )

    result = service.handle_payment_result(user_id=42, payment_id="100", confirmation=confirmation)

    assert result.status == PaymentStatus.SUCCESS
    assert result.payment_id == "rzp_pay_xyz"
    assert result.amount == 29900


def test_handle_payment_result_failed_verification_is_not_an_exception():
    tool_client = StubToolClient(
        execute_results={"verify_payment": _ok({"verified": False, "message": "Signature mismatch"})}
    )
    service = RazorpayToolPaymentService(
        RazorpayPaymentToolAdapter(tool_client), OrderToolAdapter(tool_client)
    )
    confirmation = PaymentConfirmation(
        provider_order_reference="rzp_order_abc123",
        provider_payment_reference="rzp_pay_xyz",
        provider_signature="bad-signature",
    )

    result = service.handle_payment_result(user_id=42, payment_id="100", confirmation=confirmation)

    assert result.status == PaymentStatus.FAILED
    assert result.payment_id is None


def test_handle_payment_result_transport_failure_raises():
    tool_client = StubToolClient(
        execute_results={"verify_payment": _err("INTERNAL_ERROR", "boom", ToolErrorType.INTERNAL_ERROR)}
    )
    service = RazorpayToolPaymentService(
        RazorpayPaymentToolAdapter(tool_client), OrderToolAdapter(tool_client)
    )
    confirmation = PaymentConfirmation(
        provider_order_reference="rzp_order_abc123",
        provider_payment_reference="rzp_pay_xyz",
        provider_signature="sig123",
    )

    with pytest.raises(PaymentVerificationError):
        service.handle_payment_result(user_id=42, payment_id="100", confirmation=confirmation)


# ---------------------------------------------------------------------------
# MockPaymentService (sanity - used by test_transaction_orchestrator.py)
# ---------------------------------------------------------------------------

def test_mock_payment_service_is_deterministic():
    service = MockPaymentService(amount=1000, currency="INR")
    request = PaymentRequest(transaction_id="txn-1", user_id=1, payment_method="CARD", idempotency_key="req-1")

    result = service.initiate_payment(request)

    assert result.amount == 1000
    assert result.currency == "INR"
    assert result.status == PaymentStatus.PENDING
    assert len(service.initiate_calls) == 1
