from __future__ import annotations

import logging

from app.agent.agent_state import AgentState, AgentStatus
from app.agent.merchant_agent import MerchantAgent
from app.agent.orchestrator import AgentOrchestrator
from app.contracts.agent_request import AgentRequest
from app.contracts.agent_response import AgentResponse, AgentResponseStatus

logger = logging.getLogger(__name__)

# AgentState.status -> AgentResponseStatus. AgentState is the existing Agent
# Core's internal representation; this table is the *only* place that
# translation happens, so the Gateway/contract layer never needs to know
# about AgentStatus at all.
_STATUS_MAP: dict[AgentStatus, AgentResponseStatus] = {
    AgentStatus.COMPLETED: AgentResponseStatus.SUCCESS,
    AgentStatus.WAITING_FOR_USER: AgentResponseStatus.WAITING_FOR_INPUT,
    AgentStatus.FAILED: AgentResponseStatus.FAILED,
}


class MerchantAgentOrchestrator(AgentOrchestrator):
    """Concrete AgentOrchestrator backed by the existing MerchantAgent.

    This is the adapter/seam between the new Gateway contracts
    (AgentRequest/AgentResponse) and the pre-existing Agent Core
    (MerchantAgent/AgentState). It does not add any reasoning, product
    search, or policy logic of its own - it only translates between the two
    shapes, and propagates the Gateway-issued requestId through to the
    response.
    """

    def __init__(self, merchant_agent: MerchantAgent):
        self._merchant_agent = merchant_agent

    def process(self, request: AgentRequest) -> AgentResponse:
        state = self._merchant_agent.run(
            user_request=request.message,
            session_id=request.session_id,
            user_id=_coerce_user_id(request.user_id),
            request_id=request.request_id,
        )
        return _to_agent_response(request.request_id, state)


def _coerce_user_id(user_id: str) -> int:
    """MerchantAgent/AgentState carry user_id as Optional[int] today. Gateway
    clients send userId as a string identifier. Default non-numeric strings
    like 'demo-user' to integer 1 so Java Tool Layer authenticates correctly.
    """
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return 1


def _to_agent_response(request_id: str, state: AgentState) -> AgentResponse:
    mapped_status = _STATUS_MAP.get(state.status)

    if mapped_status is None:
        # Defensive: AgentLoop.run() is expected to always return a terminal
        # state (COMPLETED / FAILED / WAITING_FOR_USER). Anything else is a
        # bug in the Agent Core, not something the Gateway should mask.
        logger.error(
            "AgentState returned in non-terminal status %s for session %s",
            state.status,
            state.session_id,
        )
        return AgentResponse.failed(
            request_id=request_id,
            message="Unable to process the request",
            code="AGENT_NON_TERMINAL_STATE",
            error_message=f"Unexpected agent status: {state.status.value}",
        )

    if mapped_status == AgentResponseStatus.FAILED:
        return AgentResponse.failed(
            request_id=request_id,
            message=state.error or "Unable to process the request",
            code="AGENT_PROCESSING_ERROR",
            error_message=state.error or "Unable to process request",
        )

    return AgentResponse(
        requestId=request_id,
        status=mapped_status,
        message=state.final_response or "",
        data=None,
    )
