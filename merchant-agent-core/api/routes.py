from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.agent.agent_state import AgentStatus
from app.agent.merchant_agent import MerchantAgent

logger = logging.getLogger(__name__)

router = APIRouter()


class AgentRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: Optional[str] = Field(default=None, alias="sessionId")
    message: str
    user_id: Optional[int] = Field(default=None, alias="userId")


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId")
    status: str
    response: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"


def get_merchant_agent() -> MerchantAgent:
    """Placeholder dependency - overridden by main.py (and by tests) via
    FastAPI's dependency_overrides, so this router never has to know how a
    MerchantAgent is actually constructed."""
    raise NotImplementedError("MerchantAgent dependency was not configured")


@router.post("/agent/run", response_model=AgentRunResponse, response_model_by_alias=True)
def run_agent(request: AgentRunRequest, agent: MerchantAgent = Depends(get_merchant_agent)) -> AgentRunResponse:
    logger.info("Received agent run request for session %s", request.session_id)

    state = agent.run(
        user_request=request.message,
        session_id=request.session_id,
        user_id=request.user_id,
    )

    response_text = state.final_response
    if state.status == AgentStatus.FAILED and not response_text:
        response_text = "Something went wrong while processing this request."

    return AgentRunResponse(sessionId=state.session_id, status=state.status.value, response=response_text)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()
