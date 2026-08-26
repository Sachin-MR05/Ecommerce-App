from __future__ import annotations

from enum import Enum

from transaction.exceptions import InvalidTransactionStateError


class TransactionState(str, Enum):
    """Explicit lifecycle states for a single transaction.

    This is the deterministic backbone of the orchestrator: every workflow
    step is a transition on this state machine, and the orchestrator never
    lets a transaction progress through an undefined transition (see
    TRANSITIONS below). No LLM, tool, or caller can skip a state.
    """

    INITIATED = "INITIATED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    # ORDER_CREATING: in this system the Java Tool Layer's create_order tool
    # atomically (a) validates the cart/stock, (b) computes the authoritative
    # total from live prices, and (c) creates both the Order row and the
    # Razorpay order used to collect payment - see
    # RazorpayPaymentToolAdapter.create_checkout(). ORDER_CREATING represents
    # that single call. This intentionally happens *before* payment
    # (standard for hosted-checkout providers like Razorpay/Stripe, which
    # need an order/payment-intent id before they can collect payment).
    ORDER_CREATING = "ORDER_CREATING"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_PROCESSING = "PAYMENT_PROCESSING"
    PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    ORDER_CONFIRMED = "ORDER_CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# The only transitions the orchestrator is allowed to make. Any attempt to
# move to a state not listed here for the current state raises
# InvalidTransactionStateError instead of silently proceeding.
TRANSITIONS: dict[TransactionState, frozenset[TransactionState]] = {
    TransactionState.INITIATED: frozenset({TransactionState.VALIDATING}),
    TransactionState.VALIDATING: frozenset({TransactionState.VALIDATED, TransactionState.FAILED}),
    TransactionState.VALIDATED: frozenset({TransactionState.ORDER_CREATING, TransactionState.FAILED}),
    TransactionState.ORDER_CREATING: frozenset({TransactionState.PAYMENT_PENDING, TransactionState.FAILED}),
    TransactionState.PAYMENT_PENDING: frozenset(
        {TransactionState.PAYMENT_PROCESSING, TransactionState.CANCELLED, TransactionState.FAILED}
    ),
    TransactionState.PAYMENT_PROCESSING: frozenset(
        {TransactionState.PAYMENT_SUCCESS, TransactionState.PAYMENT_FAILED}
    ),
    TransactionState.PAYMENT_SUCCESS: frozenset({TransactionState.ORDER_CONFIRMED, TransactionState.FAILED}),
    TransactionState.PAYMENT_FAILED: frozenset({TransactionState.FAILED}),
    TransactionState.ORDER_CONFIRMED: frozenset(),
    TransactionState.FAILED: frozenset(),
    TransactionState.CANCELLED: frozenset(),
}

# Terminal states are a dead end: once reached, execute()/confirm_payment()
# never re-run business logic for that transaction again - see
# TransactionOrchestrator's idempotency handling.
TERMINAL_STATES: frozenset[TransactionState] = frozenset(
    {TransactionState.ORDER_CONFIRMED, TransactionState.FAILED, TransactionState.CANCELLED}
)


class TransactionStateMachine:
    """Wraps a single transaction's current TransactionState and enforces
    TRANSITIONS. Pure in-memory bookkeeping - no persistence, no I/O, no
    business logic. TransactionOrchestrator owns one of these per
    transaction (via TransactionRecord) and calls `transition()` at each
    workflow step.
    """

    def __init__(self, initial: TransactionState = TransactionState.INITIATED):
        self._state = initial

    @property
    def state(self) -> TransactionState:
        return self._state

    def can_transition(self, target: TransactionState) -> bool:
        return target in TRANSITIONS.get(self._state, frozenset())

    def transition(self, target: TransactionState) -> TransactionState:
        if not self.can_transition(target):
            raise InvalidTransactionStateError(
                f"Invalid transaction state transition: {self._state.value} -> {target.value}"
            )
        self._state = target
        return self._state

    def is_terminal(self) -> bool:
        return self._state in TERMINAL_STATES
