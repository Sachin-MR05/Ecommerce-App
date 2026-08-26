from __future__ import annotations


class TransactionError(Exception):
    """Base class for every error the Transaction Orchestrator itself
    raises. Never raised for a *business* payment/order failure (those are
    reported via a structured TransactionResult, not an exception) - only
    for requests the orchestrator refuses to process at all.
    """


class TransactionValidationError(TransactionError):
    """The TransactionRequest itself is malformed (missing/invalid fields).
    Raised before any cart, payment, or order call is made."""


class CartValidationError(TransactionError):
    """The cart/order is not in a state a transaction can be built from
    (e.g. empty cart, unavailable product, stale pricing). Surfaced by the
    Java Tool Layer's create_order tool and re-raised here as a domain
    error rather than a generic PaymentError."""


class InvalidTransactionStateError(TransactionError):
    """An operation was attempted that is not valid for the transaction's
    current TransactionState (e.g. confirming payment on a transaction that
    was never validated, or re-running a terminal transaction's workflow)."""


class OrderCreationError(TransactionError):
    """The order could not be created/confirmed for a reason unrelated to
    cart validation or payment (e.g. the order lookup/order tool failed)."""


class TransactionNotFoundError(TransactionError):
    """No transaction record exists for the given request_id/transaction_id."""
