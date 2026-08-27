from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AuditEventType(str, Enum):
    """Extensible set of lifecycle events the Audit Service can record.
    Add new values here as needed - the Audit Service itself never
    validates business meaning, only that the event carries one of these
    (or, in principle, another agreed string - see AuditEvent.event_type).
    """

    REQUEST_RECEIVED = "REQUEST_RECEIVED"
    AGENT_REQUEST = "AGENT_REQUEST"
    TOOL_CALL = "TOOL_CALL"
    TOOL_SUCCESS = "TOOL_SUCCESS"
    TOOL_FAILURE = "TOOL_FAILURE"
    PRODUCT_SEARCH = "PRODUCT_SEARCH"
    PRODUCT_SELECTED = "PRODUCT_SELECTED"
    TRANSACTION_CREATED = "TRANSACTION_CREATED"
    TRANSACTION_STARTED = "TRANSACTION_STARTED"
    PAYMENT_INITIATED = "PAYMENT_INITIATED"
    PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYMENT_TIMEOUT = "PAYMENT_TIMEOUT"
    ORDER_CREATED = "ORDER_CREATED"
    TRANSACTION_COMPLETED = "TRANSACTION_COMPLETED"
    TRANSACTION_FAILED = "TRANSACTION_FAILED"
    RETRY_STARTED = "RETRY_STARTED"
    RETRY_COMPLETED = "RETRY_COMPLETED"
    RECOVERY_STARTED = "RECOVERY_STARTED"
    RECOVERY_COMPLETED = "RECOVERY_COMPLETED"


class AuditEvent(BaseModel):
    """One immutable, append-only record of something that happened.

    Pure data, like contracts/tool_response.py: this model never decides
    anything and never persists itself - AuditService/AuditRepository own
    that. Every transaction-related event is traceable via request_id +
    transaction_id + event_id together.
    """

    model_config = ConfigDict(populate_by_name=True)

    event_id: str
    request_id: str
    transaction_id: Optional[str] = None
    event_type: AuditEventType
    component: str
    operation: str
    status: str
    timestamp: datetime
    actor: str = "system"
    metadata: dict[str, Any] = Field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    @staticmethod
    def new(
        request_id: str,
        event_type: AuditEventType,
        component: str,
        operation: str,
        status: str,
        transaction_id: Optional[str] = None,
        actor: str = "system",
        metadata: Optional[dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> "AuditEvent":
        return AuditEvent(
            event_id=f"evt-{uuid.uuid4()}",
            request_id=request_id,
            transaction_id=transaction_id,
            event_type=event_type,
            component=component,
            operation=operation,
            status=status,
            timestamp=datetime.now(timezone.utc),
            actor=actor,
            metadata=metadata or {},
            error_code=error_code,
            error_message=error_message,
        )
