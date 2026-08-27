from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from contracts.tool_error import ToolErrorType


class ErrorCategory(str, Enum):
    """Standardized failure categories used across the Failure Handling
    component. Deliberately fixed and small - every caller (Executor,
    MerchantAgent, Audit Service) branches on this set, never on a raw
    exception type or a tool-specific error code.

    Kept distinct from `contracts.tool_error.ToolErrorType`: that enum
    describes the Gateway<->Tool Layer wire contract and must not change
    lightly. ErrorCategory is the Failure Handling component's own
    vocabulary, mapped from ToolErrorType (and from ToolClient transport
    exceptions) in `classification.py`.
    """

    VALIDATION_ERROR = "VALIDATION_ERROR"
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    INVENTORY_ERROR = "INVENTORY_ERROR"
    PAYMENT_DECLINED = "PAYMENT_DECLINED"
    PAYMENT_TIMEOUT = "PAYMENT_TIMEOUT"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    NETWORK_ERROR = "NETWORK_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    TRANSACTION_ERROR = "TRANSACTION_ERROR"
    DUPLICATE_TRANSACTION = "DUPLICATE_TRANSACTION"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


# Categories that a fresh attempt might plausibly resolve. Everything else
# is treated as non-retryable by default - see RetryPolicy.should_retry,
# which still takes the final decision so this is only ever the default a
# StandardError carries when nothing more specific is known.
_DEFAULT_RETRYABLE_CATEGORIES = frozenset(
    {
        ErrorCategory.SERVICE_UNAVAILABLE,
        ErrorCategory.NETWORK_ERROR,
        ErrorCategory.DATABASE_ERROR,
        ErrorCategory.PAYMENT_TIMEOUT,
    }
)


def is_retryable_by_default(category: ErrorCategory) -> bool:
    return category in _DEFAULT_RETRYABLE_CATEGORIES


class StandardError(BaseModel):
    """Structured, standardized error information produced by the Failure
    Handling component for any failure originating in the Agent Gateway,
    Tool Layer, database operations, or Transaction/Payment execution.

    This is the internal representation used for retry/recovery decisions
    and for audit logging. `to_response()` renders the standardized,
    client-safe failure shape - never the raw exception or a stack trace.
    """

    model_config = ConfigDict(populate_by_name=True)

    error_code: str
    error_type: ErrorCategory
    message: str
    component: str
    retryable: bool
    transaction_id: Optional[str] = None
    request_id: Optional[str] = None

    def to_response(self) -> dict:
        """The standardized failure response shape returned to upstream
        callers. Never includes stack traces or internal implementation
        details - only what's needed to act on or display the failure."""
        return {
            "success": False,
            "error": {
                "code": self.error_code,
                "type": self.error_type.value,
                "message": self.message,
                "retryable": self.retryable,
            },
            "transaction_id": self.transaction_id,
            "request_id": self.request_id,
        }


# Mapping from the existing Gateway<->Tool Layer wire contract
# (ToolErrorType) to this component's ErrorCategory vocabulary. Kept in one
# place so adding a new ToolErrorType value only requires one edit here.
_TOOL_ERROR_TYPE_MAP: dict[ToolErrorType, ErrorCategory] = {
    ToolErrorType.VALIDATION_ERROR: ErrorCategory.VALIDATION_ERROR,
    ToolErrorType.NOT_FOUND: ErrorCategory.PRODUCT_NOT_FOUND,
    ToolErrorType.UNAUTHORIZED: ErrorCategory.VALIDATION_ERROR,
    ToolErrorType.FORBIDDEN: ErrorCategory.VALIDATION_ERROR,
    ToolErrorType.INVENTORY_UNAVAILABLE: ErrorCategory.INVENTORY_ERROR,
    ToolErrorType.PAYMENT_REQUIRED: ErrorCategory.PAYMENT_DECLINED,
    ToolErrorType.TOOL_EXECUTION_ERROR: ErrorCategory.TRANSACTION_ERROR,
    ToolErrorType.TIMEOUT: ErrorCategory.PAYMENT_TIMEOUT,
    ToolErrorType.INTERNAL_ERROR: ErrorCategory.INTERNAL_ERROR,
}


def category_from_tool_error_type(tool_error_type: ToolErrorType) -> ErrorCategory:
    return _TOOL_ERROR_TYPE_MAP.get(tool_error_type, ErrorCategory.UNKNOWN_ERROR)
