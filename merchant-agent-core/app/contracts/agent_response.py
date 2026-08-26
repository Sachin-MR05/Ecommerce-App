from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentResponseStatus(str, Enum):
    SUCCESS = "SUCCESS"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class AgentError(BaseModel):
    """Structured error detail. Never a raw stack trace - those stay in
    server logs only (see gateway/middleware.py and controller.py)."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class AgentResponse(BaseModel):
    """The response object that crosses the Agent Orchestrator -> Gateway
    boundary, and (after the Gateway attaches HTTP-level status codes) is
    returned to the client largely unchanged. The Gateway must not alter the
    semantic content (status/message/data) of this object - see
    tests/gateway/test_gateway_contract.py.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    request_id: str = Field(alias="requestId")
    status: AgentResponseStatus
    message: str
    data: Optional[dict[str, Any]] = None
    error: Optional[AgentError] = None

    @staticmethod
    def success(request_id: str, message: str, data: Optional[dict[str, Any]] = None) -> "AgentResponse":
        return AgentResponse(requestId=request_id, status=AgentResponseStatus.SUCCESS, message=message, data=data)

    @staticmethod
    def failed(request_id: str, message: str, code: str, error_message: Optional[str] = None) -> "AgentResponse":
        return AgentResponse(
            requestId=request_id,
            status=AgentResponseStatus.FAILED,
            message=message,
            data=None,
            error=AgentError(code=code, message=error_message or message),
        )
