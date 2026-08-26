from __future__ import annotations


class PaymentError(Exception):
    """Base class for anything that goes wrong initiating, checking, or
    verifying a payment. Never carries card numbers, CVVs, or other
    sensitive payment data - see PaymentService docstrings."""


class PaymentInitiationError(PaymentError):
    """The payment/order could not be initiated (e.g. empty cart, stock
    unavailable, provider order creation failed)."""


class PaymentTimeoutError(PaymentError):
    """The payment provider (or the Tool Layer call to it) did not respond
    in time."""


class PaymentVerificationError(PaymentError):
    """The payment result could not be verified at all (transport/provider
    failure) - distinct from a payment that was verified and found to be
    invalid/declined, which is a normal PaymentResult(status=FAILED), not
    an exception."""
