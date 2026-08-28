from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

# Payment methods this system currently knows how to route to a payment
# provider. This is deliberately small and explicit - the orchestrator must
# never silently accept a payment method it has no PaymentService support
# for. Extend this (and the wiring that picks a PaymentService) when a new
# provider/method is added; do not widen it "just in case".
SUPPORTED_PAYMENT_METHODS: frozenset[str] = frozenset({"CARD", "UPI", "NETBANKING", "WALLET"})


class TransactionRequest(BaseModel):
    """The structured request the Transaction / Payment Orchestrator
    receives once the Policy Engine has approved a checkout action.

    This is intentionally minimal. It is NOT where the cart contents or the
    payable amount live - this system has one active cart per user_id
    (see CartService/CartController in the Java Tool Layer) and no
    "get_cart" tool is exposed to the Python agent to duplicate that
    server-side, so the orchestrator never re-derives cart contents itself.
    Instead it delegates cart loading, product/quantity/availability
    validation, and authoritative total calculation to the existing
    create_order tool (MerchantCommerceAdapter.createCheckout ->
    OrderService.checkout), which already performs all of that atomically
    server-side to avoid a check-then-charge race between validation and
    payment. See transaction_orchestrator.py for exactly where that call
    happens in the workflow.

    Consequently this contract carries no `amount` or `cart_id` field: this
    model has no opinion about the price, and the orchestrator must never
    accept a client/LLM-supplied amount as authoritative (see
    PAYMENT SAFETY in the orchestrator's docstring).

    request_id     - caller-supplied idempotency key. Re-submitting the same
                      request_id never creates a second payment or order;
                      see TransactionOrchestrator's idempotency handling.
    user_id        - whose cart/order this transaction is for. Accepts the
                      same int|str shapes MerchantAgentOrchestrator already
                      handles (see app/agent/merchant_agent_orchestrator.py).
    session_id     - optional, caller-supplied identifier for the browsing/
                      chat session this checkout came from (e.g. the Agent
                      Gateway's conversation id, if the caller has one).
                      Purely informational - the orchestrator never branches
                      on it. Displays fall back to request_id when a caller
                      doesn't supply one (see monitoring/store.py), since
                      request_id is always present and unique per attempt.
    transaction_type - optional, caller-supplied label for what kind of
                      transaction this is (e.g. "checkout", "refund").
                      Purely informational, like session_id - this
                      orchestrator's workflow does not vary by it today (it
                      only implements checkout), but the field exists so a
                      future refund/reorder flow doesn't need a contract
                      change to be distinguishable in monitoring.
    currency       - optional, client-declared currency. Informational only:
                      the orchestrator cross-checks it against the
                      authoritative currency returned by the payment
                      provider call and never lets a client value override
                      it.
    payment_method - one of SUPPORTED_PAYMENT_METHODS. Forwarded to the
                      payment provider as a hint about how the checkout
                      widget should be presented; it does not change what
                      is charged.
    metadata       - optional, extensible context, mirroring the existing
                      ToolRequest.context convention (contracts/tool_request.py).
    """

    model_config = ConfigDict(populate_by_name=True)

    request_id: str = Field(..., min_length=1)
    user_id: Union[int, str] = Field(...)
    session_id: Optional[str] = None
    transaction_type: str = "checkout"
    currency: Optional[str] = None
    payment_method: str = "CARD"
    metadata: dict[str, Any] = Field(default_factory=dict)
