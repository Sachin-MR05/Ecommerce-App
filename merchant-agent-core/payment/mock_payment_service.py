from __future__ import annotations

from typing import Union

from payment.payment_confirmation import PaymentConfirmation
from payment.payment_request import PaymentRequest
from payment.payment_result import PaymentResult, PaymentStatus
from payment.payment_service import PaymentService

# ---------------------------------------------------------------------------
# FOR TESTS ONLY.
#
# This is a deterministic, in-memory fake PaymentService. It never talks to
# Razorpay, the Java Tool Layer, or any network at all, and it must never be
# wired into production code (see main.py/app/gateway/wiring.py, which use
# RazorpayToolPaymentService instead). It exists purely so
# TransactionOrchestrator's workflow/state-machine logic can be unit-tested
# without a running Java service or real payment provider.
# ---------------------------------------------------------------------------


class MockPaymentService(PaymentService):
    """Deterministic fake: every initiated payment gets a fixed amount/
    currency (configurable at construction) and either always succeeds or
    always fails verification, depending on `verification_result`.
    """

    def __init__(
        self,
        amount: int = 150000,
        currency: str = "INR",
        verification_result: bool = True,
    ):
        self._amount = amount
        self._currency = currency
        self._verification_result = verification_result
        self.initiate_calls: list[PaymentRequest] = []
        self.verify_calls: list[tuple[Union[int, str], str, PaymentConfirmation]] = []
        self._orders: dict[str, dict] = {}

    def initiate_payment(self, request: PaymentRequest) -> PaymentResult:
        self.initiate_calls.append(request)
        order_id = f"order-{len(self.initiate_calls)}"
        provider_reference = f"mock_provider_order_{len(self.initiate_calls)}"
        self._orders[order_id] = {"status": "CREATED", "amount": self._amount, "currency": self._currency}
        return PaymentResult(
            payment_id=None,
            status=PaymentStatus.PENDING,
            amount=self._amount,
            currency=self._currency,
            provider_reference=provider_reference,
            message="Mock payment order created.",
            metadata={"order_id": order_id, "key_id": "mock_key"},
        )

    def get_payment_status(self, user_id: Union[int, str], payment_id: str) -> PaymentResult:
        order = self._orders.get(payment_id, {"status": "CREATED", "amount": self._amount, "currency": self._currency})
        status_map = {"CREATED": PaymentStatus.PENDING, "PAID": PaymentStatus.SUCCESS, "FAILED": PaymentStatus.FAILED}
        return PaymentResult(
            payment_id=None,
            status=status_map[order["status"]],
            amount=order["amount"],
            currency=order["currency"],
        )

    def handle_payment_result(
        self, user_id: Union[int, str], payment_id: str, confirmation: PaymentConfirmation
    ) -> PaymentResult:
        self.verify_calls.append((user_id, payment_id, confirmation))

        if not self._verification_result:
            if payment_id in self._orders:
                self._orders[payment_id]["status"] = "FAILED"
            return PaymentResult(
                payment_id=None,
                status=PaymentStatus.FAILED,
                amount=0,
                currency="",
                provider_reference=confirmation.provider_order_reference,
                message="Mock verification failed.",
            )

        if payment_id in self._orders:
            self._orders[payment_id]["status"] = "PAID"

        return PaymentResult(
            payment_id=confirmation.provider_payment_reference,
            status=PaymentStatus.SUCCESS,
            amount=self._amount,
            currency=self._currency,
            provider_reference=confirmation.provider_order_reference,
            message="Mock payment verified.",
            metadata={"order_id": payment_id},
        )
