from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from audit.audit_event import AuditEvent, AuditEventType
from audit.audit_repository import AuditRepository, InMemoryAuditRepository

logger = logging.getLogger(__name__)

AuditEventListener = Callable[[AuditEvent], None]


class AuditService:
    """Centralized recorder of system/transaction lifecycle events.

    Records what happened - never decides anything. Failure Handling (and
    every other component) calls `record_event` after it has already made
    its own decision; the Audit Service does not evaluate, retry, or
    reject that decision, it only logs it durably and makes it traceable
    by request_id/transaction_id/event_id.

    Optional observers (`add_listener`) are notified, in-process, with the
    same AuditEvent right after it is appended. This is the seam the
    monitoring module (see monitoring/wiring.py) uses to build a real-time
    view of the system without this service knowing monitoring exists, and
    without any caller of `record_event` changing - a listener exception is
    caught and logged so a misbehaving observer can never break the actual
    audit trail or the caller's request.
    """

    def __init__(self, repository: Optional[AuditRepository] = None):
        self._repository = repository or InMemoryAuditRepository()
        self._listeners: list[AuditEventListener] = []

    def add_listener(self, listener: AuditEventListener) -> None:
        self._listeners.append(listener)

    def record_event(
        self,
        event_type: AuditEventType,
        component: str,
        operation: str,
        status: str,
        request_id: str,
        transaction_id: Optional[str] = None,
        actor: str = "system",
        metadata: Optional[dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> AuditEvent:
        event = AuditEvent.new(
            request_id=request_id,
            event_type=event_type,
            component=component,
            operation=operation,
            status=status,
            transaction_id=transaction_id,
            actor=actor,
            metadata=metadata,
            error_code=error_code,
            error_message=error_message,
        )
        self._repository.append(event)
        logger.info(
            "AUDIT %s component=%s operation=%s status=%s request_id=%s transaction_id=%s event_id=%s",
            event.event_type.value,
            component,
            operation,
            status,
            request_id,
            transaction_id,
            event.event_id,
        )
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:  # noqa: BLE001 - a listener must never break audit recording
                logger.exception("AuditEvent listener raised; continuing")
        return event

    def get_transaction_history(self, transaction_id: str) -> list[AuditEvent]:
        """The complete, time-ordered audit trail for one transaction."""
        events = self._repository.get_by_transaction(transaction_id)
        return sorted(events, key=lambda e: e.timestamp)
