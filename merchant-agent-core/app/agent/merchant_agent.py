from __future__ import annotations

import logging
from typing import Optional

from app.agent.agent_loop import AgentLoop
from app.agent.agent_state import AgentState
from app.execution.executor import Executor
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
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_client: ToolClient,
        prompt_manager: Optional[PromptManager] = None,
        max_iterations: int = 10,
    ):
        self._tool_client = tool_client
        self._prompt_manager = prompt_manager or PromptManager()
        self._planner = Planner(llm_client, self._prompt_manager)
        self._executor = Executor(tool_client)
        self._agent_loop = AgentLoop(self._planner, self._executor, max_iterations)

    def run(self, user_request: str, session_id: Optional[str] = None, user_id: Optional[int] = None) -> AgentState:
        state = AgentState.create(user_request=user_request, session_id=session_id, user_id=user_id)
        state.add_message("user", user_request)

        logger.info("Starting agent run for session %s", state.session_id)

        try:
            state.available_tools = self._tool_client.get_available_tools()
        except ToolClientError as exc:
            logger.error("Could not load available tools for session %s: %s", state.session_id, exc)
            state.fail("The commerce tool service is currently unavailable. Please try again shortly.")
            return state

        if not state.available_tools:
            logger.error("No tools available from the Java Tool Layer for session %s", state.session_id)
            state.fail("No commerce tools are currently available. Please try again shortly.")
            return state

        return self._agent_loop.run(state)
