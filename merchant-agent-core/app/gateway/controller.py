from __future__ import annotations

import logging

from app.agent.orchestrator import AgentOrchestrator
from app.contracts.agent_request import AgentRequest
from app.contracts.agent_response import AgentResponse

logger = logging.getLogger(__name__)


class AgentProcessingError(Exception):
    """Raised when the AgentOrchestrator fails unexpectedly. The Gateway
    route layer turns this into a structured HTTP 500 - the real exception
    (with stack trace) only ever reaches the server logs, never the
    client."""


class AgentGatewayController:
    """Coordinates the Gateway-side flow:

        AgentRequest -> AgentOrchestrator.process() -> AgentResponse

    This is the only place in the Gateway that talks to the Agent Core, and
    it does so purely through the AgentOrchestrator abstraction - it has no
    knowledge of MerchantAgent, LLMs, tools, or policies. It depends on the
    orchestrator via constructor injection (see gateway/routes.py's
    dependency wiring) rather than constructing one itself.
    """

    def __init__(self, orchestrator: AgentOrchestrator):
        self._orchestrator = orchestrator

    def handle_request(self, request: AgentRequest) -> AgentResponse:
        try:
            response = self._orchestrator.process(request)
        except Exception as exc:  # noqa: BLE001 - deliberately broad: any
            # unhandled Agent Core exception must not leak past the Gateway
            # boundary as a raw traceback to the client.
            logger.exception(
                "Unhandled error from AgentOrchestrator for requestId=%s sessionId=%s",
                request.request_id,
                request.session_id,
            )
            raise AgentProcessingError(str(exc)) from exc

        if response.request_id != request.request_id:
            # The Gateway establishes the correlation id; the orchestrator
            # must not lose it, but if it ever does (e.g. a bug downstream),
            # restore it here rather than returning a mismatched contract to
            # the client.
            logger.warning(
                "AgentOrchestrator returned mismatched requestId (%s != %s); correcting",
                response.request_id,
                request.request_id,
            )
            response = response.model_copy(update={"request_id": request.request_id})

        return response
