import time

import pytest

from failure_handling.classification import classify_tool_error
from failure_handling.error_types import ErrorCategory, StandardError
from failure_handling.failure_handler import FailureHandler
from failure_handling.idempotency import (
    DuplicateOperationInProgressError,
    IdempotencyStatus,
    IdempotencyStore,
)
from failure_handling.recovery import RecoveryAction
from failure_handling.retry_policy import RetryConfig, RetryPolicy
from failure_handling.timeout_handler import TimeoutHandler, TransactionStatus
from app.tools.tool_client import (
    ToolClientError,
    ToolServiceTimeoutError,
    ToolServiceUnavailableError,
)
from contracts.tool_error import ToolError, ToolErrorType


def _error(retryable: bool, category: ErrorCategory = ErrorCategory.SERVICE_UNAVAILABLE) -> StandardError:
    return StandardError(
        error_code="SOME_ERROR",
        error_type=category,
        message="something went wrong",
        component="TestComponent",
        retryable=retryable,
        transaction_id="txn-1",
        request_id="req-1",
    )


# ---------------------------------------------------------------------------
# 1. Retryable error -> retry
# ---------------------------------------------------------------------------


def test_retryable_error_is_retried_on_first_attempt():
    policy = RetryPolicy(RetryConfig(max_retries=3))
    error = _error(retryable=True)

    assert policy.should_retry(error, attempt=1) is True


# ---------------------------------------------------------------------------
# 2. Non-retryable error -> no retry
# ---------------------------------------------------------------------------


def test_non_retryable_error_is_never_retried():
    policy = RetryPolicy(RetryConfig(max_retries=3))
    error = _error(retryable=False)

    assert policy.should_retry(error, attempt=1) is False
    assert policy.should_retry(error, attempt=2) is False


# ---------------------------------------------------------------------------
# 3. Max retry limit
# ---------------------------------------------------------------------------


def test_max_retry_limit_stops_after_configured_attempts():
    # attempt 1 -> failure, attempt 2 -> retry, attempt 3 -> retry, attempt 4 -> stop
    policy = RetryPolicy(RetryConfig(max_retries=3))
    error = _error(retryable=True)

    assert policy.should_retry(error, attempt=1) is True  # 1st retry allowed
    assert policy.should_retry(error, attempt=2) is True  # 2nd retry allowed
    assert policy.should_retry(error, attempt=3) is True  # 3rd retry allowed
    assert policy.should_retry(error, attempt=4) is False  # 4th would exceed max_retries


# ---------------------------------------------------------------------------
# 4. Exponential backoff calculation
# ---------------------------------------------------------------------------


def test_exponential_backoff_delay_grows_per_attempt():
    policy = RetryPolicy(RetryConfig(max_retries=5, base_delay_seconds=1.0, backoff_multiplier=2.0, max_delay_seconds=100.0))

    assert policy.next_attempt_delay(attempt=1) == 1.0
    assert policy.next_attempt_delay(attempt=2) == 2.0
    assert policy.next_attempt_delay(attempt=3) == 4.0
    assert policy.next_attempt_delay(attempt=4) == 8.0


def test_exponential_backoff_delay_is_capped():
    policy = RetryPolicy(RetryConfig(max_retries=10, base_delay_seconds=1.0, backoff_multiplier=2.0, max_delay_seconds=5.0))

    assert policy.next_attempt_delay(attempt=5) == 5.0  # would be 16.0 uncapped


# ---------------------------------------------------------------------------
# 5. Payment timeout handling
# ---------------------------------------------------------------------------


def test_timeout_confirmed_success_recovers_without_treating_as_failure():
    handler = TimeoutHandler()

    result = handler.check_after_timeout(
        status_check=lambda: TransactionStatus.SUCCESS,
        component="PaymentOrchestrator",
        transaction_id="txn-1",
        request_id="req-1",
    )

    assert result.action == RecoveryAction.RECOVER
    assert result.standard_error is None


def test_timeout_confirmed_pending_is_not_a_hard_failure():
    handler = TimeoutHandler()

    result = handler.check_after_timeout(
        status_check=lambda: TransactionStatus.PENDING,
        component="PaymentOrchestrator",
        transaction_id="txn-1",
        request_id="req-1",
    )

    assert result.action == RecoveryAction.PENDING
    assert result.standard_error.retryable is False


def test_timeout_confirmed_failed_maps_to_fail():
    handler = TimeoutHandler()

    result = handler.check_after_timeout(
        status_check=lambda: TransactionStatus.FAILED,
        component="PaymentOrchestrator",
        transaction_id="txn-1",
        request_id="req-1",
    )

    assert result.action == RecoveryAction.FAIL
    assert result.standard_error.error_code == "PAYMENT_TIMEOUT"


def test_timeout_unknown_status_is_never_guessed_as_success_or_failure():
    handler = TimeoutHandler()

    result = handler.check_after_timeout(
        status_check=lambda: TransactionStatus.UNKNOWN,
        component="PaymentOrchestrator",
    )

    assert result.action == RecoveryAction.UNKNOWN


def test_timeout_status_check_raising_is_treated_as_unknown_not_crashed():
    handler = TimeoutHandler()

    def boom():
        raise RuntimeError("status service down")

    result = handler.check_after_timeout(status_check=boom, component="PaymentOrchestrator")

    assert result.action == RecoveryAction.UNKNOWN


# ---------------------------------------------------------------------------
# 6. Duplicate transaction detection
# ---------------------------------------------------------------------------


def test_duplicate_transaction_with_same_key_is_detected_while_in_progress():
    store = IdempotencyStore()
    key = store.build_key("create_order", "txn-1", {"cartId": 1})

    store.begin(key, "txn-1", "create_order")

    with pytest.raises(DuplicateOperationInProgressError):
        store.begin(key, "txn-1", "create_order")


def test_duplicate_key_is_stable_for_identical_arguments():
    key_a = IdempotencyStore.build_key("create_order", None, {"cartId": 1, "userId": 7})
    key_b = IdempotencyStore.build_key("create_order", None, {"userId": 7, "cartId": 1})  # different order

    assert key_a == key_b


def test_different_arguments_produce_different_keys():
    key_a = IdempotencyStore.build_key("create_order", None, {"cartId": 1})
    key_b = IdempotencyStore.build_key("create_order", None, {"cartId": 2})

    assert key_a != key_b


# ---------------------------------------------------------------------------
# 7. Idempotency protection
# ---------------------------------------------------------------------------


def test_idempotency_protection_returns_cached_result_for_succeeded_operation():
    store = IdempotencyStore()
    key = store.build_key("verify_payment", "txn-1", {"orderId": 5})

    record = store.begin(key, "txn-1", "verify_payment")
    assert record.status == IdempotencyStatus.IN_PROGRESS

    store.complete(key, {"transactionId": "txn-1", "verified": True})

    replayed = store.begin(key, "txn-1", "verify_payment")
    assert replayed.status == IdempotencyStatus.SUCCEEDED
    assert replayed.result == {"transactionId": "txn-1", "verified": True}


def test_idempotency_protection_returns_failed_record_without_reexecuting():
    store = IdempotencyStore()
    key = store.build_key("verify_payment", "txn-2", {"orderId": 6})

    store.begin(key, "txn-2", "verify_payment")
    store.fail(key, "Payment declined by processor")

    replayed = store.begin(key, "txn-2", "verify_payment")
    assert replayed.status == IdempotencyStatus.FAILED
    assert replayed.error == "Payment declined by processor"


def test_idempotency_store_returns_none_for_unknown_key():
    store = IdempotencyStore()

    assert store.get("does-not-exist") is None


# ---------------------------------------------------------------------------
# 8. Standardized error response
# ---------------------------------------------------------------------------


def test_standard_error_renders_the_documented_response_shape():
    error = StandardError(
        error_code="PAYMENT_TIMEOUT",
        error_type=ErrorCategory.PAYMENT_TIMEOUT,
        message="Payment status could not be confirmed",
        component="PaymentOrchestrator",
        retryable=False,
        transaction_id="txn-1",
        request_id="req-1",
    )

    response = error.to_response()

    assert response == {
        "success": False,
        "error": {
            "code": "PAYMENT_TIMEOUT",
            "type": "PAYMENT_TIMEOUT",
            "message": "Payment status could not be confirmed",
            "retryable": False,
        },
        "transaction_id": "txn-1",
        "request_id": "req-1",
    }


def test_standard_error_response_never_includes_stack_trace_fields():
    error = StandardError(
        error_code="INTERNAL_ERROR",
        error_type=ErrorCategory.INTERNAL_ERROR,
        message="An unexpected error occurred",
        component="Executor",
        retryable=False,
    )

    response = error.to_response()

    assert "traceback" not in response
    assert "stack_trace" not in str(response).lower()


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def test_classify_tool_error_maps_payment_required_to_payment_declined():
    tool_error = ToolError(code="PAYMENT_DECLINED", message="Card declined", type=ToolErrorType.PAYMENT_REQUIRED)

    standard_error = classify_tool_error(tool_error, component="Executor", transaction_id="txn-1", request_id="req-1")

    assert standard_error.error_type == ErrorCategory.PAYMENT_DECLINED
    assert standard_error.retryable is False  # PAYMENT_DECLINED is not retryable by default


def test_classify_tool_error_maps_inventory_unavailable():
    tool_error = ToolError(code="OUT_OF_STOCK", message="No stock", type=ToolErrorType.INVENTORY_UNAVAILABLE)

    standard_error = classify_tool_error(tool_error, component="Executor")

    assert standard_error.error_type == ErrorCategory.INVENTORY_ERROR


# ---------------------------------------------------------------------------
# FailureHandler - end-to-end decision making
# ---------------------------------------------------------------------------


def test_failure_handler_retries_transport_timeout_then_fails_after_max_retries():
    handler = FailureHandler(retry_policy=RetryPolicy(RetryConfig(max_retries=2)))
    exc = ToolServiceTimeoutError("timed out")

    first = handler.handle_tool_client_exception(exc, component="Executor", attempt=1, request_id="req-1")
    second = handler.handle_tool_client_exception(exc, component="Executor", attempt=2, request_id="req-1")
    third = handler.handle_tool_client_exception(exc, component="Executor", attempt=3, request_id="req-1")

    assert first.action == RecoveryAction.RETRY
    assert second.action == RecoveryAction.RETRY
    assert third.action == RecoveryAction.FAIL


def test_failure_handler_never_retries_validation_error():
    handler = FailureHandler()
    tool_error = ToolError(code="VALIDATION_ERROR", message="Missing field", type=ToolErrorType.VALIDATION_ERROR)

    result = handler.handle_tool_error(tool_error, component="Executor", attempt=1, request_id="req-1")

    assert result.action == RecoveryAction.FAIL


def test_failure_handler_classifies_service_unavailable_as_retryable():
    handler = FailureHandler()
    exc = ToolServiceUnavailableError("tool layer down")

    result = handler.handle_tool_client_exception(exc, component="Executor", attempt=1, request_id="req-1")

    assert result.action == RecoveryAction.RETRY
    assert result.standard_error.error_type == ErrorCategory.SERVICE_UNAVAILABLE


def test_failure_handler_protected_operation_lifecycle():
    handler = FailureHandler()
    key = handler.idempotency_key_for("create_order", "txn-9", {"cartId": 1})

    record = handler.begin_protected_operation(key, "txn-9", "create_order")
    assert record.status == IdempotencyStatus.IN_PROGRESS

    handler.complete_protected_operation(key, {"orderId": "ORD-9"})

    replayed = handler.begin_protected_operation(key, "txn-9", "create_order")
    assert replayed.status == IdempotencyStatus.SUCCEEDED
    assert replayed.result == {"orderId": "ORD-9"}
