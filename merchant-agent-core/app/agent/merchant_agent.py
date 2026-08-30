from __future__ import annotations

import logging
from typing import Optional

from app.agent.agent_loop import AgentLoop
from app.agent.agent_state import AgentState
from audit.audit_event import AuditEventType
from audit.audit_service import AuditService
from app.execution.executor import Executor
from failure_handling.failure_handler import FailureHandler
from app.llm.llm_client import LLMClient, LLMUnavailableError
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
        self._session_history = {}

    def run(
        self,
        user_request: str,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None,
        request_id: Optional[str] = None,
    ) -> AgentState:
        # Load previous session history if available
        prev_messages = []
        prev_prod_id = None
        prev_qty = None
        if session_id and session_id in self._session_history:
            history = self._session_history[session_id]
            prev_messages = history.get("messages", [])
            prev_prod_id = history.get("selected_product_id")
            prev_qty = history.get("selected_quantity")

        state = AgentState.create(
            user_request=user_request, session_id=session_id, user_id=user_id, request_id=request_id
        )
        for msg in prev_messages:
            state.messages.append(msg)
        state.selected_product_id = prev_prod_id
        state.selected_quantity = prev_qty

        state.add_message("user", user_request)

        logger.info("Starting agent run for session %s", state.session_id)
        self._audit(AuditEventType.REQUEST_RECEIVED, state, status="RECEIVED")

        try:
            state.available_tools = self._tool_client.get_available_tools()
        except ToolClientError as exc:
            logger.error("Could not load available tools for session %s: %s", state.session_id, exc)
            state.fail("The commerce tool service is currently unavailable. Please try again shortly.")
            self._audit(AuditEventType.TRANSACTION_FAILED, state, status="FAILED", error_message=str(exc))
            self._save_session_history(session_id, state)
            return state

        if not state.available_tools:
            logger.error("No tools available from the Java Tool Layer for session %s", state.session_id)
            state.fail("No commerce tools are currently available. Please try again shortly.")
            self._audit(AuditEventType.TRANSACTION_FAILED, state, status="FAILED", error_message=state.error)
            self._save_session_history(session_id, state)
            return state

        try:
            result_state = self._agent_loop.run(state)
        except LLMUnavailableError as exc:
            # Mirrors the ToolClientError handling above: an LLM provider
            # outage/timeout is a real, expected failure mode (rate limits,
            # provider downtime, network issues) - not a bug - and must
            # degrade the same way a tool-service outage does: a clear
            # buyer-facing message, a TRANSACTION_FAILED audit event so it's
            # visible in monitoring/failures and can trigger the failure-rate
            # alert, and a 200-with-FAILED-status Gateway response rather
            # than an opaque 500. Before this, an LLM outage propagated
            # uncaught past this method entirely: no audit event was
            # recorded (the request effectively vanished from the audit
            # trail after REQUEST_RECEIVED), and the caller saw a generic
            # AGENT_PROCESSING_ERROR 500 instead of a graceful failure -
            # found by live-testing this endpoint with the LLM provider
            # unreachable.
            logger.error("LLM provider unavailable for session %s: %s", state.session_id, exc)
            state.fail("The assistant is temporarily unavailable. Please try again shortly.")
            self._audit(AuditEventType.TRANSACTION_FAILED, state, status="FAILED", error_message=str(exc))
            self._save_session_history(session_id, state)
            return state

        if result_state.status.value == "COMPLETED":
            self._audit(AuditEventType.TRANSACTION_COMPLETED, result_state, status="SUCCESS")
        elif result_state.status.value == "FAILED":
            self._audit(
                AuditEventType.TRANSACTION_FAILED, result_state, status="FAILED", error_message=result_state.error
            )

        self._save_session_history(session_id, result_state)
        return result_state

    def _save_session_history(self, session_id: Optional[str], state: AgentState) -> None:
        if session_id:
            self._session_history[session_id] = {
                "messages": state.messages,
                "selected_product_id": state.selected_product_id,
                "selected_quantity": state.selected_quantity
            }

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
