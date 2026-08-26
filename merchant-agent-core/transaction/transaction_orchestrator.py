from __future__ import annotations

import logging
from typing import Optional

from payment.exceptions import PaymentError
from payment.payment_confirmation import PaymentConfirmation
from payment.payment_request import PaymentRequest
from payment.payment_result import PaymentStatus
from payment.payment_service import PaymentService
from transaction.exceptions import (
    CartValidationError,
    InvalidTransactionStateError,
    TransactionNotFoundError,
    TransactionValidationError,
)
from transaction.transaction_request import TransactionRequest
from transaction.transaction_result import PendingPaymentAction, TransactionErrorPayload, TransactionResult
from transaction.transaction_service import TransactionValidationService
from transaction.transaction_state import TERMINAL_STATES, TransactionState
from transaction.transaction_store import InMemoryTransactionStore, TransactionRecord, TransactionStore

logger = logging.getLogger(__name__)


class TransactionOrchestrator:
    """Deterministic coordinator for a single commerce transaction.

    ==========================================================================
    WHERE THIS SITS
    ==========================================================================
    User -> Agent Gateway -> Merchant Agent Core -> LLM/Agent -> Policy Engine
         -> **Transaction / Payment Orchestrator** -> Tools -> Merchant Backend

    The LLM decides *what* the user wants (e.g. "checkout") and the Policy
    Engine decides whether that's *allowed*. By the time a TransactionRequest
    reaches this class, both of those decisions have already been made -
    this class contains no LLM calls, no prompts, no product search, and no
    business-policy logic (e.g. fraud thresholds, spend limits). It only
    coordinates a fixed, deterministic sequence of steps and enforces the
    TransactionState machine (transaction_state.py) around them.

    ==========================================================================
    WORKFLOW
    ==========================================================================
    execute(request):
      1. Idempotency check (see PAYMENT SAFETY below).
      2. INITIATED -> VALIDATING -> VALIDATED: validate the request shape.
      3. authorization_check(): the future Approval Gate insertion point
         (see below) - currently a pass-through.
      4. VALIDATED -> ORDER_CREATING -> PAYMENT_PENDING: call
         PaymentService.initiate_payment(), which (via the existing
         create_order tool) atomically loads the cart, validates
         products/quantities/availability, computes the authoritative
         total, and creates a payment order to collect payment against.
      5. Return a TransactionResult with a `pending_action` describing what
         the caller must hand to the payment provider's checkout widget.

    confirm_payment(request_id, confirmation):
      6. PAYMENT_PENDING -> PAYMENT_PROCESSING -> PAYMENT_SUCCESS /
         PAYMENT_FAILED: call PaymentService.handle_payment_result(), which
         re-verifies the payment server-side.
      7. On success: PAYMENT_SUCCESS -> ORDER_CONFIRMED. (Order confirmation
         is a side effect already performed inside
         handle_payment_result() in this system - see
         RazorpayToolPaymentService - so no separate order-confirmation
         call happens here.)
      8. On failure: PAYMENT_FAILED -> FAILED. An order is never created
         (or left) in a confirmed state after a failed payment.

    Why two entry points instead of one execute() that runs start-to-finish:
    this system's payment provider (Razorpay) is a hosted-checkout
    integration - the user completes payment out-of-band, in a widget, on
    the frontend. The orchestrator cannot synchronously wait for that; it
    hands back what the widget needs and is later invoked again (as
    confirm_payment) once the widget reports completion. A payment provider
    that supported a fully server-side, synchronous charge could use a
    single execute() that internally called both steps - PaymentService is
    the seam that would let that swap happen without touching this
    workflow's structure.

    ==========================================================================
    FUTURE APPROVAL GATE EXTENSION POINT
    ==========================================================================
    authorization_check() is called once, right after VALIDATED and before
    any payment/order tool call is made. It is currently a no-op that logs
    and returns - it does NOT implement approval logic, does NOT decide
    whether approval is required (that is the Policy Engine's job), and
    does NOT hardcode any threshold.

    Later, this single call site becomes:

        TransactionOrchestrator
              |
        validate transaction
              |
        (payment amount becomes known via ORDER_CREATING)
              |
        authorization_check()  <-- becomes a call into the Approval Gate
              |                     - APPROVED: continue exactly as today
              |                     - WAITING_FOR_APPROVAL: orchestrator
              |                       transitions to a (new) WAITING state
              |                       instead of ORDER_CREATING/PAYMENT_PENDING
              v
            Payment

    Because this is a single, clearly named call site (not scattered
    inline checks), inserting the Approval Gate later means implementing
    its logic and changing what authorization_check() does - not
    redesigning execute()'s control flow.

    ==========================================================================
    PAYMENT SAFETY / IDEMPOTENCY
    ==========================================================================
    Every transaction is keyed by TransactionRequest.request_id in a
    TransactionStore. execute() called twice with the same request_id never
    initiates a second payment: it returns the stored result (whatever
    state that transaction has reached) instead of re-running any step.
    confirm_payment() behaves the same way for a transaction that has
    already reached a terminal state (ORDER_CONFIRMED/FAILED/CANCELLED) - it
    replays the stored result rather than re-verifying payment or
    re-confirming the order.

    ==========================================================================
    AUTHORITATIVE AMOUNT
    ==========================================================================
    This class never accepts an amount from TransactionRequest (there isn't
    one - see transaction_request.py) or from the LLM. The only amount ever
    recorded on a transaction is whatever PaymentService returns, which is
    itself derived from trusted cart/order data server-side.
    """

    def __init__(
        self,
        payment_service: PaymentService,
        validation_service: Optional[TransactionValidationService] = None,
        store: Optional[TransactionStore] = None,
    ):
        self._payment_service = payment_service
        self._validation_service = validation_service or TransactionValidationService()
        self._store = store or InMemoryTransactionStore()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, request: TransactionRequest) -> TransactionResult:
        existing = self._store.get(request.request_id)
        if existing is not None:
            logger.info(
                "Idempotent replay of execute() for request_id=%s (already %s)",
                request.request_id,
                existing.state.value,
            )
            return self._to_result(existing)

        record = TransactionRecord.new(request.request_id, request.user_id)
        self._store.save(record)
        logger.info("Transaction started transaction_id=%s user_id=%s", record.transaction_id, request.user_id)

        record.state_machine.transition(TransactionState.VALIDATING)
        try:
            self._validation_service.validate(request)
        except TransactionValidationError as exc:
            return self._fail(record, code="VALIDATION_FAILED", message=str(exc))

        record.state_machine.transition(TransactionState.VALIDATED)
        logger.info("Transaction validated transaction_id=%s", record.transaction_id)

        self._authorization_check(record)

        record.state_machine.transition(TransactionState.ORDER_CREATING)
        payment_request = PaymentRequest(
            transaction_id=record.transaction_id,
            user_id=request.user_id,
            payment_method=request.payment_method,
            idempotency_key=request.request_id,
            metadata=request.metadata,
        )
        try:
            payment_result = self._payment_service.initiate_payment(payment_request)
        except CartValidationError as exc:
            return self._fail(record, code="CART_VALIDATION_FAILED", message=str(exc))
        except PaymentError as exc:
            return self._fail(record, code="PAYMENT_INITIATION_FAILED", message=str(exc))

        try:
            self._validation_service.reconcile_currency(request.currency, payment_result.currency)
        except TransactionValidationError as exc:
            return self._fail(record, code="CURRENCY_MISMATCH", message=str(exc))

        record.amount = payment_result.amount
        record.currency = payment_result.currency
        record.order_id = payment_result.metadata.get("order_id")
        record.provider_order_reference = payment_result.provider_reference
        record.provider_key_id = payment_result.metadata.get("key_id")
        logger.info(
            "Transaction amount calculated transaction_id=%s amount=%s currency=%s",
            record.transaction_id,
            record.amount,
            record.currency,
        )

        record.state_machine.transition(TransactionState.PAYMENT_PENDING)
        logger.info(
            "Payment initiated transaction_id=%s provider_reference=%s",
            record.transaction_id,
            record.provider_order_reference,
        )

        self._store.save(record)
        return self._to_result(record)

    def confirm_payment(self, request_id: str, confirmation: PaymentConfirmation) -> TransactionResult:
        record = self._store.get(request_id)
        if record is None:
            raise TransactionNotFoundError(f"No transaction found for request_id={request_id}")

        if record.state in TERMINAL_STATES:
            logger.info(
                "Idempotent replay of confirm_payment() for transaction_id=%s (already %s)",
                record.transaction_id,
                record.state.value,
            )
            return self._to_result(record)

        if record.state != TransactionState.PAYMENT_PENDING:
            raise InvalidTransactionStateError(
                f"Cannot confirm payment for transaction_id={record.transaction_id} while in state "
                f"{record.state.value}"
            )

        record.state_machine.transition(TransactionState.PAYMENT_PROCESSING)
        logger.info("Payment result processing transaction_id=%s", record.transaction_id)

        try:
            payment_result = self._payment_service.handle_payment_result(
                user_id=record.user_id,
                payment_id=record.order_id,
                confirmation=confirmation,
            )
        except PaymentError as exc:
            logger.warning("Payment verification could not be completed transaction_id=%s: %s", record.transaction_id, exc)
            return self._fail_payment(record, message=str(exc))

        if payment_result.status != PaymentStatus.SUCCESS:
            logger.warning(
                "Payment not verified transaction_id=%s message=%s", record.transaction_id, payment_result.message
            )
            return self._fail_payment(record, message=payment_result.message or "Payment could not be completed.")

        record.state_machine.transition(TransactionState.PAYMENT_SUCCESS)
        record.payment_id = payment_result.payment_id
        logger.info("Payment succeeded transaction_id=%s payment_id=%s", record.transaction_id, record.payment_id)

        # Order confirmation is a side effect PaymentService.handle_payment_result()
        # already performed (see RazorpayToolPaymentService) - no separate
        # order-confirmation tool call happens here.
        record.state_machine.transition(TransactionState.ORDER_CONFIRMED)
        logger.info("Order confirmed transaction_id=%s order_id=%s", record.transaction_id, record.order_id)

        self._store.save(record)
        return self._to_result(record)

    # ------------------------------------------------------------------
    # Future Approval Gate insertion point
    # ------------------------------------------------------------------

    def _authorization_check(self, record: TransactionRecord) -> None:
        """FUTURE APPROVAL GATE INSERTION POINT - see class docstring.

        Currently allows every validated transaction to proceed
        unconditionally. Does not implement approval logic, does not
        decide whether approval is required, and does not hardcode any
        threshold - that decision belongs to the Policy Engine / future
        Approval Gate, not this orchestrator.
        """
        logger.info(
            "Authorization checkpoint reached transaction_id=%s (no Approval Gate configured; continuing)",
            record.transaction_id,
        )
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fail(self, record: TransactionRecord, *, code: str, message: str) -> TransactionResult:
        record.state_machine.transition(TransactionState.FAILED)
        record.error = {"code": code, "message": message}
        self._store.save(record)
        logger.warning("Transaction failed transaction_id=%s code=%s", record.transaction_id, code)
        return self._to_result(record)

    def _fail_payment(self, record: TransactionRecord, *, message: str) -> TransactionResult:
        record.state_machine.transition(TransactionState.PAYMENT_FAILED)
        record.state_machine.transition(TransactionState.FAILED)
        record.error = {"code": "PAYMENT_FAILED", "message": message}
        self._store.save(record)
        return self._to_result(record)

    def _to_result(self, record: TransactionRecord) -> TransactionResult:
        pending_action = None
        if record.state == TransactionState.PAYMENT_PENDING and record.provider_order_reference:
            pending_action = PendingPaymentAction(
                provider="RAZORPAY",
                provider_order_reference=record.provider_order_reference,
                key_id=record.provider_key_id,
            )

        error = TransactionErrorPayload(**record.error) if record.error else None

        return TransactionResult(
            success=record.state == TransactionState.ORDER_CONFIRMED,
            transaction_id=record.transaction_id,
            status=record.state,
            order_id=record.order_id,
            payment_id=record.payment_id,
            amount=record.amount,
            currency=record.currency,
            pending_action=pending_action,
            error=error,
        )
