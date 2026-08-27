from __future__ import annotations

import logging

from app.agent.agent_state import AgentState
from app.planning.decision import Decision
from app.tools.tool_client import ToolClient, ToolClientError
from app.tools.tool_schema import ToolCallResult, ToolDefinition

logger = logging.getLogger(__name__)


class ExecutorError(Exception):
    """A tool call could not be executed as decided."""


class UnknownToolError(ExecutorError):
    """The planner selected a tool that isn't in the request's available tool definitions."""


class InvalidToolArgumentsError(ExecutorError):
    """The supplied arguments don't satisfy the tool's declared input schema."""


class Executor:
    """Executes a validated TOOL_CALL Decision against the Java Tool Layer
    via ToolClient, and records the outcome on the AgentState.

    Never decides which tool to use - that belongs to the planner/LLM. This
    class only validates that the chosen tool/arguments are legitimate,
    delegates, and captures the result.
    """

    def __init__(self, tool_client: ToolClient):
        self._tool_client = tool_client

    def execute(self, decision: Decision, state: AgentState) -> ToolCallResult:
        tool_definition = self._require_known_tool(decision.tool_name, state.available_tools)
        self._validate_arguments(tool_definition, decision.arguments)

        state.record_tool_call(decision.tool_name, decision.arguments)
        logger.info("Executing tool '%s' for session %s", decision.tool_name, state.session_id)

        try:
            result = self._tool_client.execute_tool(decision.tool_name, decision.arguments, user_id=state.user_id)
        except ToolClientError as exc:
            logger.error("Tool '%s' execution failed: %s", decision.tool_name, exc)
            state.record_tool_error(str(exc))
            raise ExecutorError(str(exc)) from exc

        state.record_tool_result(result)
        return result

    def _require_known_tool(self, tool_name: str, available_tools: list[ToolDefinition]) -> ToolDefinition:
        for tool in available_tools:
            if tool.name == tool_name:
                return tool
        raise UnknownToolError(f"Tool '{tool_name}' is not among the tools available for this request")

    def _validate_arguments(self, tool: ToolDefinition, arguments: dict) -> None:
        required = tool.input_schema.get("required", []) if isinstance(tool.input_schema, dict) else []
        missing = [name for name in required if name not in arguments]
        if missing:
            raise InvalidToolArgumentsError(
                f"Tool '{tool.name}' is missing required argument(s): {', '.join(missing)}"
            )
