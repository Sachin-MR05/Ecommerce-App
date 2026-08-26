from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Union

from payment.exceptions import PaymentError, PaymentInitiationError, PaymentVerificationError
from payment.payment_confirmation import PaymentConfirmation
from payment.payment_request import PaymentRequest
from payment.payment_result import PaymentResult, PaymentStatus
from tools.order.order_tool_adapter import OrderToolAdapter
from tools.payment.razorpay_payment_tool_adapter import RazorpayPaymentToolAdapter

logger = logging.getLogger(__name__)


class PaymentService(ABC):
    """The only payment-provider-facing interface TransactionOrchestrator
    depends on. The orchestrator never imports Razorpay-specific (or any
    other provider's) types or tool names directly - only this contract -
    so swapping/adding a payment provider never requires touching
    transaction_orchestrator.py.
    """

    @abstractmethod
    def initiate_payment(self, request: PaymentRequest) -> PaymentResult:
        """Start collecting payment for a transaction. Implementations are
        responsible for obtaining/validating the authoritative amount
        themselves (e.g. from trusted cart data) - PaymentRequest carries
        no client-supplied amount to trust in the first place.
        Raises PaymentError (or a subclass) if payment could not be
        initiated at all; never raises for an ordinary "cart empty" style
        business rejection surfaced as CartValidationError by the caller -
        see transaction_orchestrator.py's mapping.
        """
        raise NotImplementedError

    @abstractmethod
    def get_payment_status(self, user_id: Union[int, str], payment_id: str) -> PaymentResult:
        """Look up the current status of a previously initiated payment/
        order, independent of handle_payment_result(). Useful for
        reconciliation or polling; not on the primary checkout path."""
        raise NotImplementedError

    @abstractmethod
    def handle_payment_result(
        self, user_id: Union[int, str], payment_id: str, confirmation: PaymentConfirmation
    ) -> PaymentResult:
        """Process the caller-supplied confirmation of a completed payment
        attempt (e.g. from a hosted checkout widget), verifying it against
        the provider rather than trusting it at face value. Returns a
        PaymentResult with status SUCCESS or FAILED - a failed
        verification is a normal result, not an exception. Raises
        PaymentError only when verification itself could not be performed
        (e.g. the provider/service was unreachable).
        """
        raise NotImplementedError


class RazorpayToolPaymentService(PaymentService):
    """Production PaymentService, backed by the existing Razorpay
    integration in the Java Tool Layer (reached via
    RazorpayPaymentToolAdapter / ToolClient - see contracts/README.md).

    Contains no Razorpay SDK usage and no signature-verification logic
    itself - all of that already lives server-side in
    OrderService/RazorpayService. This class only shapes payment/-layer
    requests and results around that existing, trusted integration.
    """

    def __init__(self, payment_tool_adapter: RazorpayPaymentToolAdapter, order_tool_adapter: OrderToolAdapter):
        self._payment_tool_adapter = payment_tool_adapter
        self._order_tool_adapter = order_tool_adapter

    def initiate_payment(self, request: PaymentRequest) -> PaymentResult:
        checkout = self._payment_tool_adapter.create_checkout(
            user_id=request.user_id,
            request_id=request.idempotency_key,
        )

        return PaymentResult(
            payment_id=None,
            status=PaymentStatus.PENDING,
            amount=checkout["amount"],
            currency=checkout["currency"],
            provider_reference=checkout["razorpayOrderId"],
            message="Payment order created; awaiting completion via the checkout widget.",
            metadata={"order_id": str(checkout["orderId"]), "key_id": checkout.get("keyId")},
        )

    def get_payment_status(self, user_id: Union[int, str], payment_id: str) -> PaymentResult:
        # `payment_id` here is the internal order_id (see
        # PaymentResult.metadata["order_id"] on initiate_payment) - this
        # system has no direct "payment status" tool, only order status,
        # which is an accurate proxy (CREATED/PAID/FAILED map 1:1 onto
        # PENDING/SUCCESS/FAILED).
        order = self._order_tool_adapter.get_order(user_id=user_id, order_id=payment_id)
        status_map = {
            "CREATED": PaymentStatus.PENDING,
            "PAID": PaymentStatus.SUCCESS,
            "FAILED": PaymentStatus.FAILED,
        }
        amount_major = order.get("totalAmount", 0)
        return PaymentResult(
            payment_id=order.get("razorpayPaymentId"),
            status=status_map.get(order.get("status"), PaymentStatus.PENDING),
            amount=round(amount_major * 100),
            currency="INR",
            provider_reference=order.get("razorpayOrderId"),
            metadata={"order_id": str(order.get("id"))},
        )

    def handle_payment_result(
        self, user_id: Union[int, str], payment_id: str, confirmation: PaymentConfirmation
    ) -> PaymentResult:
        try:
            result = self._payment_tool_adapter.verify_payment(
                user_id=user_id,
                provider_order_reference=confirmation.provider_order_reference,
                provider_payment_reference=confirmation.provider_payment_reference,
                provider_signature=confirmation.provider_signature,
                request_id=payment_id,
            )
        except PaymentVerificationError:
            raise

        if not result.get("verified"):
            return PaymentResult(
                payment_id=None,
                status=PaymentStatus.FAILED,
                amount=0,
                currency="",
                provider_reference=confirmation.provider_order_reference,
                message=result.get("message") or "Payment could not be verified.",
            )

        order = result.get("order") or {}
        return PaymentResult(
            payment_id=confirmation.provider_payment_reference,
            status=PaymentStatus.SUCCESS,
            amount=round(order.get("totalAmount", 0) * 100),
            currency="INR",
            provider_reference=confirmation.provider_order_reference,
            message=result.get("message") or "Payment verified.",
            metadata={"order_id": str(order.get("id"))} if order.get("id") is not None else {},
        )
