from __future__ import annotations

import logging
from typing import Any, Optional

from failure_handling.classification import (
    classify_tool_client_exception,
    classify_tool_error,
    classify_unexpected_exception,
)
from failure_handling.error_types import StandardError
from failure_handling.idempotency import (
    DuplicateOperationInProgressError,
    IdempotencyRecord,
    IdempotencyStore,
)
from failure_handling.recovery import RecoveryAction, RecoveryResult
from failure_handling.retry_policy import RetryPolicy
from app.tools.tool_client import ToolClientError
from contracts.tool_error import ToolError

logger = logging.getLogger(__name__)


class FailureHandler:
    """Centralized, deterministic failure handling for the Agent Gateway,
    Tool Layer, database operations, and Transaction/Payment execution.

    No decision made here ever depends on an LLM call - every method is
    plain, deterministic Python logic operating on structured inputs
    (exceptions, ToolError payloads, attempt counters). This is the single
    place upstream components ask "what do I do about this failure?".
    """

    def __init__(
        self,
        retry_policy: Optional[RetryPolicy] = None,
        idempotency_store: Optional[IdempotencyStore] = None,
    ):
        self._retry_policy = retry_policy or RetryPolicy()
        self._idempotency_store = idempotency_store or IdempotencyStore()

    @property
    def idempotency_store(self) -> IdempotencyStore:
        return self._idempotency_store

    @property
    def retry_policy(self) -> RetryPolicy:
        return self._retry_policy

    # ------------------------------------------------------------------
    # Classification + recovery decision
    # ------------------------------------------------------------------

    def handle_tool_client_exception(
        self,
        exc: ToolClientError,
        component: str,
        attempt: int,
        transaction_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> RecoveryResult:
        """A transport-level failure calling the Java Tool Layer (timeout,
        service unavailable, malformed response, etc.)."""
        error = classify_tool_client_exception(exc, component, transaction_id, request_id)
        return self._decide(error, attempt)

    def handle_tool_error(
        self,
        tool_error: ToolError,
        component: str,
        attempt: int,
        transaction_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> RecoveryResult:
        """A business-level tool failure (ToolResponse.success=False)."""
        error = classify_tool_error(tool_error, component, transaction_id, request_id)
        return self._decide(error, attempt)

    def handle_unexpected_exception(
        self,
        exc: Exception,
        component: str,
        attempt: int,
        transaction_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> RecoveryResult:
        """Anything not already recognized by a more specific classifier
        (e.g. a database driver error). Always classified as
        non-retryable UNKNOWN_ERROR unless a caller has already handled
        it more specifically."""
        error = classify_unexpected_exception(exc, component, transaction_id, request_id)
        return self._decide(error, attempt)

    def _decide(self, error: StandardError, attempt: int) -> RecoveryResult:
        if self._retry_policy.should_retry(error, attempt):
            return RecoveryResult(
                action=RecoveryAction.RETRY,
                reason=f"{error.error_type.value} is retryable (attempt {attempt})",
                standard_error=error,
            )
        return RecoveryResult(
            action=RecoveryAction.FAIL,
            reason=f"{error.error_type.value} is not retryable or max attempts reached (attempt {attempt})",
            standard_error=error,
        )

    def next_attempt_delay(self, attempt: int) -> float:
        return self._retry_policy.next_attempt_delay(attempt)

    # ------------------------------------------------------------------
    # Idempotency protection
    # ------------------------------------------------------------------

    def idempotency_key_for(
        self, operation_type: str, transaction_id: Optional[str], arguments: dict[str, Any]
    ) -> str:
        return IdempotencyStore.build_key(operation_type, transaction_id, arguments)

    def begin_protected_operation(
        self, idempotency_key: str, transaction_id: Optional[str], operation_type: str
    ) -> IdempotencyRecord:
        """Raises DuplicateOperationInProgressError if the same operation
        is already running; returns the existing record (SUCCEEDED/FAILED)
        if this operation already ran to completion, so the caller can
        short-circuit instead of re-executing a payment/order/transaction."""
        return self._idempotency_store.begin(idempotency_key, transaction_id, operation_type)

    def complete_protected_operation(self, idempotency_key: str, result: Any) -> None:
        self._idempotency_store.complete(idempotency_key, result)

    def fail_protected_operation(self, idempotency_key: str, error: str) -> None:
        self._idempotency_store.fail(idempotency_key, error)


__all__ = [
    "FailureHandler",
    "DuplicateOperationInProgressError",
]
