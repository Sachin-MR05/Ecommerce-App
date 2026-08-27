from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolErrorType(str, Enum):
    """Small, fixed set of error categories every caller can branch on
    generically, independent of the tool-specific ToolError.code. Kept
    deliberately small - add a value only when an entire class of callers
    needs to treat it differently, not for every new failure mode a
    specific tool might have.
    """

    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INVENTORY_UNAVAILABLE = "INVENTORY_UNAVAILABLE"
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"
    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ToolError(BaseModel):
    """Standardized error payload carried on ToolResponse.error when
    success is false.

    Pure data: this class never decides what to do about an error, logs
    anything, or maps from an internal exception - it only describes one.
    That translation is the Tool Layer's job (or the Agent Core's, on
    receipt), not this contract's.

    code    - specific, tool/domain-level identifier (e.g. "PRODUCT_NOT_FOUND").
              Free-form by design - the contract does not enumerate every
              possible code, since new tools introduce new specific failures.
    type    - coarse category from ToolErrorType - what a caller branches
              on generically, independent of which tool/code produced it.
    message - human/LLM-readable explanation.
    details - optional, arbitrary structured context. Never required.
    """

    model_config = ConfigDict(populate_by_name=True)

    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    type: ToolErrorType
    details: dict[str, Any] = Field(default_factory=dict)
