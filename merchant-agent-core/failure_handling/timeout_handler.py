from __future__ import annotations

import logging
from enum import Enum
from typing import Callable, Optional

from failure_handling.error_types import ErrorCategory, StandardError
from failure_handling.recovery import RecoveryAction, RecoveryResult

logger = logging.getLogger(__name__)


class TransactionStatus(str, Enum):
    """The actual state of a transaction/payment, as confirmed by a
    status-check call (e.g. the `verify_payment` tool) - never assumed
    from the timeout itself."""

    SUCCESS = "SUCCESS"
    PENDING = "PENDING"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


StatusCheckFn = Callable[[], TransactionStatus]


class TimeoutHandler:
    """Handles operation timeouts explicitly.

    A timeout must never be treated as an automatic payment/transaction
    failure: the request may have succeeded on the far side even though
    the response never arrived. This class always requires the caller to
    confirm the real status (e.g. via a `verify_payment`/order-status tool
    call) before producing a recovery decision - it never guesses.
    """

    def check_after_timeout(
        self,
        status_check: StatusCheckFn,
        component: str,
        transaction_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> RecoveryResult:
        """PAYMENT_REQUEST -> TIMEOUT -> check transaction status ->
        SUCCESS -> RECOVER, PENDING -> PENDING, FAILED -> FAIL,
        UNKNOWN -> UNKNOWN (never guessed as success or failure)."""
        try:
            status = status_check()
        except Exception as exc:  # noqa: BLE001 - the status check itself
            # failing must not crash the timeout handler; treat it as an
            # unknown outcome rather than propagating.
            logger.error(
                "Status check after timeout raised for transaction_id=%s: %s", transaction_id, exc
            )
            status = TransactionStatus.UNKNOWN

        if status == TransactionStatus.SUCCESS:
            return RecoveryResult(
                action=RecoveryAction.RECOVER,
                reason="Transaction confirmed successful after timeout",
                transaction_status=status.value,
            )

        if status == TransactionStatus.PENDING:
            return RecoveryResult(
                action=RecoveryAction.PENDING,
                reason="Transaction status still pending reconciliation after timeout",
                transaction_status=status.value,
                standard_error=StandardError(
                    error_code="PAYMENT_TIMEOUT",
                    error_type=ErrorCategory.PAYMENT_TIMEOUT,
                    message="Payment status could not be confirmed yet; reconciliation pending",
                    component=component,
                    retryable=False,
                    transaction_id=transaction_id,
                    request_id=request_id,
                ),
            )

        if status == TransactionStatus.FAILED:
            return RecoveryResult(
                action=RecoveryAction.FAIL,
                reason="Transaction confirmed failed after timeout",
                transaction_status=status.value,
                standard_error=StandardError(
                    error_code="PAYMENT_TIMEOUT",
                    error_type=ErrorCategory.PAYMENT_TIMEOUT,
                    message="Payment status could not be confirmed",
                    component=component,
                    retryable=False,
                    transaction_id=transaction_id,
                    request_id=request_id,
                ),
            )

        return RecoveryResult(
            action=RecoveryAction.UNKNOWN,
            reason="Transaction status could not be determined after timeout",
            transaction_status=TransactionStatus.UNKNOWN.value,
            standard_error=StandardError(
                error_code="PAYMENT_TIMEOUT",
                error_type=ErrorCategory.PAYMENT_TIMEOUT,
                message="Payment status is unknown after timeout; manual reconciliation required",
                component=component,
                retryable=False,
                transaction_id=transaction_id,
                request_id=request_id,
            ),
        )
