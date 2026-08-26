from __future__ import annotations

from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field


class PaymentRequest(BaseModel):
    """What TransactionOrchestrator asks a PaymentService to initiate.

    Deliberately carries no `amount` - PaymentService.initiate_payment()
    implementations for this system compute/obtain the authoritative amount
    themselves (via the trusted cart/order data), and the orchestrator
    treats whatever comes back on PaymentResult as authoritative. Never
    add an amount field here that a caller could set: doing so would
    reopen the exact "never trust the client's total" gap this design
    closes.
    """

    model_config = ConfigDict(populate_by_name=True)

    transaction_id: str = Field(..., min_length=1)
    user_id: Union[int, str]
    payment_method: str
    idempotency_key: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
