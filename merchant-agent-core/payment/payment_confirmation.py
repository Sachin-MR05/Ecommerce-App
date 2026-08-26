from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PaymentConfirmation(BaseModel):
    """What the caller (frontend/Gateway) hands back after the user
    completes a payment provider's hosted checkout widget.

    Named generically (provider_order_reference / provider_payment_reference
    / provider_signature) rather than after Razorpay's field names, so
    PaymentService stays a provider-agnostic interface - see
    payment_service.py. A concrete adapter (e.g.
    RazorpayPaymentToolAdapter) is the only place that maps these onto a
    specific provider's wire fields (razorpayOrderId/razorpayPaymentId/
    razorpaySignature).
    """

    model_config = ConfigDict(populate_by_name=True)

    provider_order_reference: str = Field(..., min_length=1)
    provider_payment_reference: str = Field(..., min_length=1)
    provider_signature: str = Field(..., min_length=1)
