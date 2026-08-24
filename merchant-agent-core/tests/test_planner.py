import json

import pytest

from app.agent.agent_state import AgentState
from app.llm.llm_client import LLMClient, LLMResponse
from app.llm.prompt_manager import PromptManager
from app.planning.decision import DecisionAction
from app.planning.planner import Planner, PlannerError
from app.tools.tool_schema import ToolDefinition


class StubLLMClient(LLMClient):
    """Returns a fixed, pre-scripted response - no real LLM call is made."""

    def __init__(self, content: str):
        self._content = content

    def generate(self, messages, tools=None) -> LLMResponse:
        return LLMResponse(content=self._content)


def _state_with_tools() -> AgentState:
    state = AgentState.create(user_request="find headphones")
    state.available_tools = [
        ToolDefinition(name="search_products", description="search the catalog", input_schema={})
    ]
    return state


def test_planner_returns_tool_call_decision():
    content = json.dumps(
        {"action": "TOOL_CALL", "tool_name": "search_products", "arguments": {"keyword": "headphones"}}
    )
    planner = Planner(StubLLMClient(content), PromptManager())

    decision = planner.decide(_state_with_tools())

    assert decision.action == DecisionAction.TOOL_CALL
    assert decision.tool_name == "search_products"
    assert decision.arguments == {"keyword": "headphones"}


def test_planner_returns_final_response_decision():
    content = json.dumps({"action": "FINAL_RESPONSE", "response": "Here you go."})
    planner = Planner(StubLLMClient(content), PromptManager())

    decision = planner.decide(_state_with_tools())

    assert decision.action == DecisionAction.FINAL_RESPONSE
    assert decision.response == "Here you go."


def test_planner_returns_ask_user_decision():
    content = json.dumps({"action": "ASK_USER", "clarification_question": "Which size?"})
    planner = Planner(StubLLMClient(content), PromptManager())

    decision = planner.decide(_state_with_tools())

    assert decision.action == DecisionAction.ASK_USER
    assert decision.clarification_question == "Which size?"


def test_planner_strips_markdown_fences_before_parsing():
    content = "```json\n" + json.dumps({"action": "FINAL_RESPONSE", "response": "Done."}) + "\n```"
    planner = Planner(StubLLMClient(content), PromptManager())

    decision = planner.decide(_state_with_tools())

    assert decision.action == DecisionAction.FINAL_RESPONSE
    assert decision.response == "Done."


def test_planner_raises_on_invalid_json():
    planner = Planner(StubLLMClient("this is not json"), PromptManager())

    with pytest.raises(PlannerError):
        planner.decide(_state_with_tools())


def test_planner_raises_on_invalid_decision_shape():
    content = json.dumps({"action": "TOOL_CALL"})  # missing required tool_name
    planner = Planner(StubLLMClient(content), PromptManager())

    with pytest.raises(PlannerError):
        planner.decide(_state_with_tools())


def test_planner_raises_on_unknown_action():
    content = json.dumps({"action": "DO_SOMETHING_ELSE"})
    planner = Planner(StubLLMClient(content), PromptManager())

    with pytest.raises(PlannerError):
        planner.decide(_state_with_tools())
