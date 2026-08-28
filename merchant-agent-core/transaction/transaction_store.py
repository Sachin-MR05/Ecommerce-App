from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Union

from transaction.transaction_state import TransactionState, TransactionStateMachine


@dataclass
class TransactionRecord:
    """Internal, mutable bookkeeping for one transaction.

    This is the orchestrator's own in-process view of a transaction - it is
    NOT the TransactionResult (the public, immutable contract returned to
    callers) and it is NOT a database row. The orchestrator contains no
    database-specific business logic itself: a TransactionStore is a small
    seam so a real implementation (e.g. backed by a table/cache) can be
    swapped in later without touching TransactionOrchestrator.
    """

    request_id: str
    transaction_id: str
    user_id: Union[int, str]
    session_id: Optional[str] = None
    transaction_type: str = "checkout"

    state_machine: TransactionStateMachine = field(default_factory=TransactionStateMachine)

    order_id: Optional[str] = None
    amount: Optional[int] = None
    currency: Optional[str] = None
    payment_id: Optional[str] = None
    provider_order_reference: Optional[str] = None
    provider_key_id: Optional[str] = None
    error: Optional[dict[str, str]] = None

    @staticmethod
    def new(
        request_id: str,
        user_id: Union[int, str],
        session_id: Optional[str] = None,
        transaction_type: str = "checkout",
    ) -> "TransactionRecord":
        return TransactionRecord(
            request_id=request_id,
            transaction_id=f"txn-{request_id}",
            user_id=user_id,
            session_id=session_id,
            transaction_type=transaction_type,
        )

    @property
    def state(self) -> TransactionState:
        return self.state_machine.state


class TransactionStore(ABC):
    """Persistence seam for TransactionRecord, keyed by request_id.

    Kept deliberately tiny (get/save) so the orchestrator never needs to
    know whether records live in memory, a cache, or a database table.
    """

    @abstractmethod
    def get(self, request_id: str) -> Optional[TransactionRecord]:
        raise NotImplementedError

    @abstractmethod
    def save(self, record: TransactionRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[TransactionRecord]:
        """All known records, most-recently-saved order not guaranteed.

        Added for read-only observability (see monitoring/), which needs to
        enumerate transactions without the orchestrator exposing anything
        beyond get/save. A future database-backed TransactionStore should
        implement this as a bounded, indexed query - not a full table scan.
        """
        raise NotImplementedError


class InMemoryTransactionStore(TransactionStore):
    """Default TransactionStore for tests, local development, and a single
    process instance. NOT durable across process restarts and NOT safe for
    multiple orchestrator processes sharing the same transactions - swap in
    a persistent TransactionStore implementation (backed by whatever
    database the rest of the project already uses) before relying on
    idempotency across processes/restarts.
    """

    def __init__(self) -> None:
        self._records: dict[str, TransactionRecord] = {}

    def get(self, request_id: str) -> Optional[TransactionRecord]:
        return self._records.get(request_id)

    def save(self, record: TransactionRecord) -> None:
        self._records[record.request_id] = record

    def list_all(self) -> list[TransactionRecord]:
        return list(self._records.values())
