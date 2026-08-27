from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class IdempotencyStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass
class IdempotencyRecord:
    """One tracked operation, keyed by idempotency_key.

    result carries whatever the operation produced on success (e.g. the
    ToolCallResult data) so a duplicate request can be answered from this
    record instead of re-executing the operation.
    """

    idempotency_key: str
    transaction_id: Optional[str]
    operation_type: str
    status: IdempotencyStatus
    result: Any = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DuplicateOperationInProgressError(Exception):
    """Raised when the same idempotency_key is already IN_PROGRESS - the
    caller must not start a second concurrent execution of the same
    payment/order/transaction operation."""


class IdempotencyStore:
    """In-memory, thread-safe idempotency tracking for payment, order, and
    transaction operations.

    This guards the Python agent-side execution path against issuing the
    same mutating tool call twice for the same logical operation (e.g. an
    agent retry re-invoking `create_order` or `verify_payment`). It is
    deliberately process-local: the Java Tool Layer / commerce backend
    remains the system of record for whether a payment actually happened,
    and should enforce its own idempotency at the database level. This
    store prevents the Python service from being the source of a duplicate
    call in the first place.
    """

    def __init__(self):
        self._records: dict[str, IdempotencyRecord] = {}
        self._lock = threading.Lock()

    @staticmethod
    def build_key(operation_type: str, transaction_id: Optional[str], arguments: dict[str, Any]) -> str:
        """Deterministic idempotency key from the operation's identity.
        Prefers a stable transaction_id when available; otherwise derives
        a stable hash from the operation type + arguments so identical
        requests collide and near-duplicates don't."""
        if transaction_id:
            return f"{operation_type}:{transaction_id}"
        payload = json.dumps(arguments, sort_keys=True, default=str)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
        return f"{operation_type}:{digest}"

    def begin(self, idempotency_key: str, transaction_id: Optional[str], operation_type: str) -> IdempotencyRecord:
        """Register the start of an operation. If a record already exists:
          - SUCCEEDED/FAILED -> returned as-is (caller should short-circuit
            and reuse it rather than re-executing).
          - IN_PROGRESS       -> raises DuplicateOperationInProgressError.
        Otherwise creates and returns a new IN_PROGRESS record."""
        with self._lock:
            existing = self._records.get(idempotency_key)
            if existing is not None:
                if existing.status == IdempotencyStatus.IN_PROGRESS:
                    raise DuplicateOperationInProgressError(
                        f"Operation '{operation_type}' with key '{idempotency_key}' is already in progress"
                    )
                return existing

            record = IdempotencyRecord(
                idempotency_key=idempotency_key,
                transaction_id=transaction_id,
                operation_type=operation_type,
                status=IdempotencyStatus.IN_PROGRESS,
            )
            self._records[idempotency_key] = record
            return record

    def get(self, idempotency_key: str) -> Optional[IdempotencyRecord]:
        with self._lock:
            return self._records.get(idempotency_key)

    def complete(self, idempotency_key: str, result: Any) -> None:
        with self._lock:
            record = self._records.get(idempotency_key)
            if record is None:
                return
            record.status = IdempotencyStatus.SUCCEEDED
            record.result = result
            record.updated_at = datetime.now(timezone.utc)

    def fail(self, idempotency_key: str, error: str) -> None:
        with self._lock:
            record = self._records.get(idempotency_key)
            if record is None:
                return
            record.status = IdempotencyStatus.FAILED
            record.error = error
            record.updated_at = datetime.now(timezone.utc)
