
from __future__ import annotations

import json
import logging
from typing import Any

from app.agent.agent_state import AgentState
from app.llm.llm_client import LLMClient, LLMMessage, LLMUnavailableError
from app.llm.prompt_manager import PromptManager
from app.planning.decision import Decision
from app.tools.tool_schema import ToolDefinition

logger = logging.getLogger(__name__)


class PlannerError(Exception):
    """The LLM's output could not be turned into a valid Decision."""


class Planner:
    """Turns the current AgentState into the next structured Decision.

    Only reasons about WHAT to do next:
      current state -> LLM -> structured Decision

    It never executes a tool, never calls a merchant API, and contains no
    HTTP code for talking to Java - that is Executor/ToolClient's job.
    """

    def __init__(self, llm_client: LLMClient, prompt_manager: PromptManager):
        self._llm_client = llm_client
        self._prompt_manager = prompt_manager

    def decide(self, state: AgentState) -> Decision:
        messages = self._build_messages(state)
        tool_definitions = self._to_llm_tool_definitions(state.available_tools)

        try:
            llm_response = self._llm_client.generate(messages, tools=tool_definitions)
        except LLMUnavailableError:
            raise
        except Exception as exc:  # unexpected provider-specific failure
            logger.exception("Unexpected error calling the LLM")
            raise PlannerError(f"Unexpected error calling the LLM: {exc}") from exc

        return self._parse_decision(llm_response.content)

    def _build_messages(self, state: AgentState) -> list[LLMMessage]:
        system_message = LLMMessage(role="system", content=self._system_prompt(state))
        return [system_message, *state.messages]

    def _system_prompt(self, state: AgentState) -> str:
        base_prompt = self._prompt_manager.get_system_prompt()
        response_contract = (
            "\nRespond with a single JSON object only - no prose, no markdown fences - matching "
            "exactly one of these shapes:\n"
            '{"action": "TOOL_CALL", "tool_name": "<tool name>", "arguments": { ... }, '
            '"rationale": "<short reason, optional>"}\n'
            '{"action": "FINAL_RESPONSE", "response": "<final answer for the user>"}\n'
            '{"action": "ASK_USER", "clarification_question": "<question for the user>"}\n'
            '{"action": "SELECT_PRODUCT", "selected_product_id": <int>, "selected_quantity": <int>}\n\n'
            f"Tools available for this request: {[t.name for t in state.available_tools]}\n"
        )
        return base_prompt + response_contract

    def _to_llm_tool_definitions(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        return [
            {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema}
            for tool in tools
        ]

    def _parse_decision(self, raw_content: str) -> Decision:
        content = raw_content.strip()
        if content.startswith("```"):
            content = content.strip("`")
            content = content.split("\n", 1)[-1] if "\n" in content else content

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("LLM response was not valid JSON")
            raise PlannerError("Malformed LLM response: expected a single JSON object") from exc

        try:
            return Decision.model_validate(payload)
        except Exception as exc:
            logger.error("LLM response did not match the Decision schema: %s", payload)
            raise PlannerError(f"Malformed LLM decision: {exc}") from exc
