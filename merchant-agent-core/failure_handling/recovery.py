from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict

from failure_handling.error_types import StandardError


class RecoveryAction(str, Enum):
    """The deterministic outcome of a failure. Always decided by plain
    Python logic in FailureHandler - never by the LLM."""

    RETRY = "RETRY"
    FAIL = "FAIL"
    RECOVER = "RECOVER"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"


class RecoveryResult(BaseModel):
    """The result of a recovery decision: what should happen next, and
    why. `standard_error` is populated whenever the outcome carries an
    error (FAIL, PENDING, UNKNOWN); it is None for RETRY/RECOVER."""

    model_config = ConfigDict(populate_by_name=True)

    action: RecoveryAction
    reason: str
    standard_error: Optional[StandardError] = None
    transaction_status: Optional[str] = None
