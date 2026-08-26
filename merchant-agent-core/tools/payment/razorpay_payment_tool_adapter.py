from __future__ import annotations

import logging
from typing import Any, Union

from app.tools.tool_client import ToolClient, ToolClientError
from payment.exceptions import PaymentInitiationError, PaymentTimeoutError, PaymentVerificationError

logger = logging.getLogger(__name__)


def _coerce_user_id(user_id: Union[int, str]) -> Union[int, str]:
    """Same coercion MerchantAgentOrchestrator already applies (see
    app/agent/merchant_agent_orchestrator.py._coerce_user_id) - the Java
    Tool Layer's ToolRequest context expects a numeric userId where
    possible, and falls back to the raw value rather than raising, so an
    unusual id shape surfaces as a normal tool/business failure instead of
    a crash here.
    """
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return user_id


class RazorpayPaymentToolAdapter:
    """The ONLY place in the transaction/payment layer that talks to the
    Java Tool Layer's payment-related tools (create_order, verify_payment)
    via the existing ToolClient.

    This is a thin translation layer: it contains no payment-provider
    business logic itself (no Razorpay SDK usage, no signature
    verification) - all of that already lives in the Java Tool Layer
    (OrderService/RazorpayService). It only shapes ToolRequest/ToolResponse
    calls and raises the payment/-layer exceptions PaymentService expects.
    """

    def __init__(self, tool_client: ToolClient):
        self._tool_client = tool_client

    def create_checkout(self, user_id: Union[int, str], request_id: str) -> dict[str, Any]:
        """Calls the create_order tool, which atomically validates the
        user's cart (availability + live pricing), computes the
        authoritative total, and creates both the Order and a matching
        Razorpay order to collect payment against.

        Returns the raw CheckoutResponse payload:
        {orderId, razorpayOrderId, amount (paise), currency, keyId}.
        Raises PaymentInitiationError for any business failure (e.g. empty
        cart, insufficient stock - surfaced by the Java Tool Layer as
        error_code "PAYMENT_ERROR").
        """
        try:
            response = self._tool_client.execute_tool(
                "create_order",
                arguments={},
                user_id=_coerce_user_id(user_id),
                request_id=request_id,
            )
        except ToolClientError as exc:
            logger.error("create_order tool call failed for request_id=%s: %s", request_id, exc)
            raise PaymentTimeoutError(f"Could not reach the payment/order service: {exc}") from exc

        if not response.success:
            logger.warning(
                "create_order reported failure for request_id=%s: %s - %s",
                request_id,
                response.error_code,
                response.error_message,
            )
            raise PaymentInitiationError(response.error_message or "Unable to create order/payment")

        return response.data

    def verify_payment(
        self,
        user_id: Union[int, str],
        provider_order_reference: str,
        provider_payment_reference: str,
        provider_signature: str,
        request_id: str,
    ) -> dict[str, Any]:
        """Calls the verify_payment tool, which re-verifies the Razorpay
        signature server-side (never trusting the client-reported success)
        and, only when genuinely valid, marks the order PAID.

        Returns the raw payload: {verified, message, order?}. Note this
        tool call itself can succeed (ToolResponse.success=True) while
        verified=False - that is a normal "payment not verified" business
        outcome, not an exception; only transport/timeout failures raise
        here.
        """
        try:
            response = self._tool_client.execute_tool(
                "verify_payment",
                arguments={
                    "razorpayOrderId": provider_order_reference,
                    "razorpayPaymentId": provider_payment_reference,
                    "razorpaySignature": provider_signature,
                },
                user_id=_coerce_user_id(user_id),
                request_id=request_id,
            )
        except ToolClientError as exc:
            logger.error("verify_payment tool call failed for request_id=%s: %s", request_id, exc)
            raise PaymentTimeoutError(f"Could not reach the payment verification service: {exc}") from exc

        if not response.success:
            logger.warning(
                "verify_payment reported failure for request_id=%s: %s - %s",
                request_id,
                response.error_code,
                response.error_message,
            )
            raise PaymentVerificationError(response.error_message or "Unable to verify payment")

        return response.data
