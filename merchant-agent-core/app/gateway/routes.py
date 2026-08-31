from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.agent.orchestrator import AgentOrchestrator
from app.contracts.agent_request import AgentRequest
from app.contracts.agent_response import AgentResponse
from app.gateway.authentication import AuthenticationError, AuthenticationService
from app.gateway.controller import AgentGatewayController, AgentProcessingError
from app.gateway.rate_limiter import RateLimiter
from app.gateway.validation import validate_incoming_message

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Wire-level request/response models.
#
# These describe what an external HTTP client sends/receives. They are
# intentionally separate from app.contracts.AgentRequest/AgentResponse (the
# internal Gateway <-> Agent Core contract): the wire shape is allowed to
# evolve (e.g. adding an `Authorization` header, omitting `requestId` on
# input) without changing the internal contract at all.
# ---------------------------------------------------------------------------
class AgentMessageHttpRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    request_id: Optional[str] = Field(default=None, alias="requestId")
    session_id: Optional[str] = Field(default=None, alias="sessionId")
    user_id: Optional[str] = Field(default=None, alias="userId")
    message: str
    channel: str = "web"


class ErrorDetail(BaseModel):
    code: str
    message: str


class AgentMessageHttpResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    request_id: str = Field(alias="requestId")
    status: str
    message: str
    data: Optional[dict] = None
    error: Optional[ErrorDetail] = None


class HealthResponse(BaseModel):
    status: str = "UP"


# ---------------------------------------------------------------------------
# Dependency providers. Each raises NotImplementedError by default and is
# overridden by main.py's dependency_overrides (and by tests) - the router
# itself never constructs an AgentOrchestrator, AuthenticationService, or
# RateLimiter.
# ---------------------------------------------------------------------------
def get_agent_orchestrator() -> AgentOrchestrator:
    raise NotImplementedError("AgentOrchestrator dependency was not configured")


def get_authentication_service() -> AuthenticationService:
    raise NotImplementedError("AuthenticationService dependency was not configured")


def get_rate_limiter() -> RateLimiter:
    raise NotImplementedError("RateLimiter dependency was not configured")


def get_gateway_controller(
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
) -> AgentGatewayController:
    return AgentGatewayController(orchestrator)


def _error_response(request_id: str, http_status: int, message: str, code: str, detail: str) -> JSONResponse:
    body = AgentMessageHttpResponse(
        requestId=request_id,
        status="FAILED",
        message=message,
        data=None,
        error=ErrorDetail(code=code, message=detail),
    )
    return JSONResponse(status_code=http_status, content=body.model_dump(by_alias=True))


def _to_http_response(response: AgentResponse) -> AgentMessageHttpResponse:
    return AgentMessageHttpResponse(
        requestId=response.request_id,
        status=response.status.value,
        message=response.message,
        data=response.data,
        error=ErrorDetail(code=response.error.code, message=response.error.message) if response.error else None,
    )


@router.post("/agent/message", response_model=AgentMessageHttpResponse, response_model_by_alias=True)
def post_agent_message(
    http_request: AgentMessageHttpRequest,
    request: Request,
    auth_service: AuthenticationService = Depends(get_authentication_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    controller: AgentGatewayController = Depends(get_gateway_controller),
):
    # The Gateway establishes the correlation id for the entire request
    # lifecycle (Gateway -> Agent Core -> Tools -> Backend). Generate it
    # before anything else so it can appear on every log line and error
    # response below, even ones produced before an AgentRequest exists.
    request_id = http_request.request_id or f"req-{uuid.uuid4()}"
    session_id = http_request.session_id or f"session-{uuid.uuid4()}"
    user_id = http_request.user_id or "1"
    request.state.request_id = request_id
    request.state.session_id = session_id
    request.state.user_id = user_id

    # 1. Authentication
    try:
        authorization = request.headers.get("authorization")
        auth_service.authenticate(authorization=authorization, user_id=user_id)
    except AuthenticationError as exc:
        return _error_response(request_id, 401, "Authentication failed", "AUTHENTICATION_FAILED", exc.message)

    # 2. Rate limiting
    if not rate_limiter.allow(user_id):
        return _error_response(
            request_id, 429, "Rate limit exceeded", "RATE_LIMIT_EXCEEDED", "Too many requests, please slow down"
        )

    # 3. Validation (deterministic, no LLM/business logic involved)
    validation_error = validate_incoming_message(
        session_id=session_id,
        user_id=user_id,
        message=http_request.message,
        channel=http_request.channel,
    )
    if validation_error is not None:
        return _error_response(request_id, 400, "Invalid request", validation_error.code, validation_error.message)

    # 4/5. Build the internal AgentRequest, propagating the requestId.
    agent_request = AgentRequest.new(
        session_id=session_id,
        user_id=user_id,
        message=http_request.message,
        channel=http_request.channel,
        request_id=request_id,
    )

    # 6/7. Hand off to the Agent Core through the Controller/Orchestrator
    # abstraction and translate the result back to the wire format.
    try:
        agent_response = controller.handle_request(agent_request)
    except AgentProcessingError:
        return _error_response(
            request_id,
            500,
            "Unable to process the request",
            "AGENT_PROCESSING_ERROR",
            "Unable to process request",
        )

    return _to_http_response(agent_response)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="UP")


@router.get("/ready", response_model=HealthResponse)
def ready() -> HealthResponse:
    return HealthResponse(status="UP")
