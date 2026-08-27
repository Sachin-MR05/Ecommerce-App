from __future__ import annotations

import logging
from typing import Optional

from app.agent.agent_loop import AgentLoop
from app.agent.agent_state import AgentState
from audit.audit_event import AuditEventType
from audit.audit_service import AuditService
from app.execution.executor import Executor
from failure_handling.failure_handler import FailureHandler
from app.llm.llm_client import LLMClient
from app.llm.prompt_manager import PromptManager
from app.planning.planner import Planner
from app.tools.tool_client import ToolClient, ToolClientError

logger = logging.getLogger(__name__)


class MerchantAgent:
    """High-level agent entry point.

    Composes LLMClient, ToolClient, Planner, Executor, AgentLoop, and
    PromptManager via constructor (dependency) injection, and runs one user
    request to completion - or to a safe stopping point (clarification
    needed, or failure). No global singletons: create a MerchantAgent per
    wiring (see main.py), and a fresh AgentState per request (see run()).

    failure_handler and audit_service are optional. When supplied, they are
    also handed to the Executor so tool-level failures/audit events are
    recorded consistently; MerchantAgent itself only records the
    request/transaction-level lifecycle events (REQUEST_RECEIVED,
    TRANSACTION_COMPLETED, TRANSACTION_FAILED) that sit above any single
    tool call.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_client: ToolClient,
        prompt_manager: Optional[PromptManager] = None,
        max_iterations: int = 10,
        failure_handler: Optional[FailureHandler] = None,
        audit_service: Optional[AuditService] = None,
    ):
        self._tool_client = tool_client
        self._prompt_manager = prompt_manager or PromptManager()
        self._failure_handler = failure_handler
        self._audit_service = audit_service
        self._planner = Planner(llm_client, self._prompt_manager)
        self._executor = Executor(tool_client, failure_handler=failure_handler, audit_service=audit_service)
        self._agent_loop = AgentLoop(self._planner, self._executor, max_iterations)

    def run(
        self,
        user_request: str,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None,
        request_id: Optional[str] = None,
    ) -> AgentState:
        state = AgentState.create(
            user_request=user_request, session_id=session_id, user_id=user_id, request_id=request_id
        )
        state.add_message("user", user_request)

        logger.info("Starting agent run for session %s", state.session_id)
        self._audit(AuditEventType.REQUEST_RECEIVED, state, status="RECEIVED")

        try:
            state.available_tools = self._tool_client.get_available_tools()
        except ToolClientError as exc:
            logger.error("Could not load available tools for session %s: %s", state.session_id, exc)
            state.fail("The commerce tool service is currently unavailable. Please try again shortly.")
            self._audit(AuditEventType.TRANSACTION_FAILED, state, status="FAILED", error_message=str(exc))
            return state

        if not state.available_tools:
            logger.error("No tools available from the Java Tool Layer for session %s", state.session_id)
            state.fail("No commerce tools are currently available. Please try again shortly.")
            self._audit(AuditEventType.TRANSACTION_FAILED, state, status="FAILED", error_message=state.error)
            return state

        result_state = self._agent_loop.run(state)

        if result_state.status.value == "COMPLETED":
            self._audit(AuditEventType.TRANSACTION_COMPLETED, result_state, status="SUCCESS")
        elif result_state.status.value == "FAILED":
            self._audit(
                AuditEventType.TRANSACTION_FAILED, result_state, status="FAILED", error_message=result_state.error
            )

        return result_state

    def _audit(
        self, event_type: AuditEventType, state: AgentState, status: str, error_message: Optional[str] = None
    ) -> None:
        if self._audit_service is None:
            return
        self._audit_service.record_event(
            event_type,
            component="MerchantAgent",
            operation="agent_run",
            status=status,
            request_id=state.request_id or state.session_id,
            error_message=error_message,
        )
