from __future__ import annotations

from transaction.exceptions import TransactionValidationError
from transaction.transaction_request import SUPPORTED_PAYMENT_METHODS, TransactionRequest


class TransactionValidationService:
    """Structural/request-shape validation only.

    Deliberately does NOT touch the cart, product catalog, or pricing -
    that validation is delegated to the existing create_order tool (see
    transaction_orchestrator.py's ORDER_CREATING step and
    TransactionRequest's docstring for why). This service only rejects
    requests the orchestrator should refuse before making any tool/payment
    call at all: missing fields, or a payment method nothing in this system
    can route.
    """

    def validate(self, request: TransactionRequest) -> None:
        if not request.request_id or not request.request_id.strip():
            raise TransactionValidationError("request_id is required")

        if request.user_id is None or (isinstance(request.user_id, str) and not request.user_id.strip()):
            raise TransactionValidationError("user_id is required")

        if request.payment_method not in SUPPORTED_PAYMENT_METHODS:
            raise TransactionValidationError(
                f"Unsupported payment_method '{request.payment_method}'. "
                f"Supported: {sorted(SUPPORTED_PAYMENT_METHODS)}"
            )

        if request.currency is not None:
            currency = request.currency.strip()
            if len(currency) != 3 or not currency.isalpha():
                raise TransactionValidationError(
                    f"currency must be a 3-letter ISO code if provided, got '{request.currency}'"
                )

    def reconcile_currency(self, requested_currency: str | None, authoritative_currency: str) -> None:
        """Cross-checks a client-declared currency against the
        authoritative currency returned by the payment provider call.
        Never lets the client value win - this only decides whether to
        raise, it never substitutes a value.
        """
        if requested_currency and requested_currency.strip().upper() != authoritative_currency.strip().upper():
            raise TransactionValidationError(
                f"Requested currency '{requested_currency}' does not match the account/cart "
                f"currency '{authoritative_currency}'"
            )
