from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from transaction.transaction_state import TransactionState


class TransactionErrorPayload(BaseModel):
    """Structured, agent/user-safe error detail. Never carries a stack
    trace or internal exception text - see TransactionOrchestrator's
    logging vs. result-payload split."""

    model_config = ConfigDict(populate_by_name=True)

    code: str
    message: str


class PendingPaymentAction(BaseModel):
    """What the caller (Gateway/frontend) needs to hand off to the payment
    provider's hosted checkout widget while a transaction sits in
    PAYMENT_PENDING. This is provider-shaped by necessity (Razorpay's
    widget needs these exact fields) but is carried as an optional,
    separate field on TransactionResult rather than baked into the core
    result shape, so swapping providers later never changes the base
    TransactionResult contract.
    """

    model_config = ConfigDict(populate_by_name=True)

    provider: str
    provider_order_reference: str
    key_id: Optional[str] = None


class TransactionResult(BaseModel):
    """The structured, deterministic outcome of a Transaction Orchestrator
    operation (execute() or confirm_payment()).

    success        - True only once the transaction is fully confirmed
                      (status == ORDER_CONFIRMED). PAYMENT_PENDING is not a
                      failure, but it is also not `success` - it is an
                      in-progress result the caller must act on (typically
                      by handing `pending_action` to a checkout widget and
                      later calling confirm_payment()).
    transaction_id - stable identifier for this transaction, derived from
                      the originating TransactionRequest.request_id.
    status         - current TransactionState, as a string.
    order_id       - the merchant order id, once known (set once
                      ORDER_CREATING has run; present even before payment
                      succeeds, since this system's order is created before
                      payment is collected - see transaction_state.py).
    payment_id     - the provider's payment reference, present only once a
                      payment attempt has actually completed
                      (PAYMENT_SUCCESS/PAYMENT_FAILED onward).
    amount/currency - the authoritative amount, exactly as returned by the
                      payment provider call - never the client/LLM-supplied
                      value (there isn't one; see TransactionRequest).
    pending_action  - present only while status == PAYMENT_PENDING.
    error           - present only when success is False and the
                      transaction has reached a terminal failure state.
    """

    model_config = ConfigDict(populate_by_name=True)

    success: bool
    transaction_id: str
    status: TransactionState
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    amount: Optional[int] = None
    currency: Optional[str] = None
    pending_action: Optional[PendingPaymentAction] = None
    error: Optional[TransactionErrorPayload] = None

    def model_dump_public(self) -> dict[str, Any]:
        """Serialises using the enum's string value for `status`, matching
        the wire examples in the design spec (e.g. "status": "FAILED")."""
        payload = self.model_dump(mode="json")
        return payload
