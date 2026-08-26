from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PaymentResult(BaseModel):
    """Structured outcome of a PaymentService call.

    payment_id         - the provider's payment reference. None until an
                          actual payment attempt has completed (a freshly
                          initiated, not-yet-paid transaction has a
                          provider_reference for the pending order/intent,
                          but no payment_id yet).
    status              - PaymentStatus.
    amount/currency     - authoritative, provider/trusted-cart-derived
                          values. Callers must never overwrite these with a
                          client-supplied amount.
    provider_reference  - the provider's identifier for the payment
                          *attempt* (e.g. a Razorpay order id) - stable
                          across initiate_payment() and
                          handle_payment_result() for the same transaction.
    message             - human/LLM-readable explanation, safe to surface.
    metadata            - provider-specific extras the orchestrator does
                          not need to interpret (e.g. a checkout widget key
                          id) but may pass through to the caller.
    """

    model_config = ConfigDict(populate_by_name=True)

    payment_id: Optional[str] = None
    status: PaymentStatus
    amount: int
    currency: str
    provider_reference: Optional[str] = None
    message: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
