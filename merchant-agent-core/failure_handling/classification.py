from __future__ import annotations

from typing import Optional

from failure_handling.error_types import (
    ErrorCategory,
    StandardError,
    category_from_tool_error_type,
    is_retryable_by_default,
)
from app.tools.tool_client import (
    MalformedToolResponseError,
    ToolClientError,
    ToolServiceTimeoutError,
    ToolServiceUnavailableError,
)
from contracts.tool_error import ToolError


def classify_tool_client_exception(
    exc: ToolClientError,
    component: str,
    transaction_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> StandardError:
    """Classify a transport-level failure raised by ToolClient (talking to
    the Java Tool Layer) into a StandardError. Never inspects a stack
    trace or exposes one - only the exception's own message, which
    ToolClient already keeps free of sensitive detail."""
    if isinstance(exc, ToolServiceTimeoutError):
        category = ErrorCategory.PAYMENT_TIMEOUT
        code = "TOOL_TIMEOUT"
    elif isinstance(exc, ToolServiceUnavailableError):
        category = ErrorCategory.SERVICE_UNAVAILABLE
        code = "TOOL_SERVICE_UNAVAILABLE"
    elif isinstance(exc, MalformedToolResponseError):
        category = ErrorCategory.INTERNAL_ERROR
        code = "MALFORMED_TOOL_RESPONSE"
    else:
        category = ErrorCategory.NETWORK_ERROR
        code = "TOOL_CLIENT_ERROR"

    return StandardError(
        error_code=code,
        error_type=category,
        message=str(exc),
        component=component,
        retryable=is_retryable_by_default(category),
        transaction_id=transaction_id,
        request_id=request_id,
    )


def classify_tool_error(
    tool_error: ToolError,
    component: str,
    transaction_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> StandardError:
    """Classify a business-level ToolResponse.error (success=false,
    HTTP 200) into a StandardError."""
    category = category_from_tool_error_type(tool_error.type)
    return StandardError(
        error_code=tool_error.code,
        error_type=category,
        message=tool_error.message,
        component=component,
        retryable=is_retryable_by_default(category),
        transaction_id=transaction_id,
        request_id=request_id,
    )


def classify_unexpected_exception(
    exc: Exception,
    component: str,
    transaction_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> StandardError:
    """Fallback classification for any exception not already recognized
    by a more specific classifier (e.g. database driver errors). Never
    includes exc's traceback - only a generic, safe message."""
    return StandardError(
        error_code="UNKNOWN_ERROR",
        error_type=ErrorCategory.UNKNOWN_ERROR,
        message="An unexpected error occurred",
        component=component,
        retryable=False,
        transaction_id=transaction_id,
        request_id=request_id,
    )
