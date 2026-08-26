from __future__ import annotations

from abc import ABC, abstractmethod

from app.contracts.agent_request import AgentRequest
from app.contracts.agent_response import AgentResponse


class AgentOrchestrator(ABC):
    """The one interface the Agent Gateway is allowed to know about.

    The Gateway must depend only on this abstraction - never on MerchantAgent,
    AgentLoop, Planner, LLMClient, ToolClient, or any other Agent Core /
    Tool Layer / Policy Engine internals. This keeps the Gateway a pure
    communication boundary (see app/gateway/*): it hands over an
    AgentRequest and receives back a fully-formed AgentResponse, without
    knowing which LLM was used, which tools were called, or how policies
    were evaluated.

    Swapping the underlying agent implementation (e.g. a new planner, a new
    LLM provider, a new tool layer) never requires touching the Gateway,
    as long as the new implementation still honors this interface.
    """

    @abstractmethod
    def process(self, request: AgentRequest) -> AgentResponse:
        """Run one AgentRequest to completion (or to a safe stopping point,
        e.g. a clarification/confirmation prompt) and return a structured
        AgentResponse. Must never raise for ordinary agent-side failures -
        those should be reported via AgentResponse(status=FAILED, error=...).
        Only truly unexpected/unhandled errors should propagate, and the
        Gateway is responsible for turning those into HTTP 500 responses.
        """
        raise NotImplementedError
