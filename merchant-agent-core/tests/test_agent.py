import json

from app.agent.agent_state import AgentStatus
from app.agent.merchant_agent import MerchantAgent
from app.llm.llm_client import LLMClient, LLMResponse
from app.tools.tool_client import ToolServiceUnavailableError
from app.tools.tool_schema import ToolCallResult, ToolDefinition


class ScriptedLLMClient(LLMClient):
    """Returns pre-scripted responses in order - no real LLM call is made."""

    def __init__(self, responses):
        self._responses = list(responses)

    def generate(self, messages, tools=None) -> LLMResponse:
        assert self._responses, "No more scripted LLM responses - test issued more iterations than expected"
        return LLMResponse(content=self._responses.pop(0))


class StubToolClient:
    """Duck-types ToolClient's public surface (get_available_tools/execute_tool)
    without making any real HTTP calls."""

    def __init__(self, tools, execute_results=None, raise_on_get_tools=None):
        self._tools = tools
        self._execute_results = execute_results or {}
        self._raise_on_get_tools = raise_on_get_tools
        self.executed_calls = []

    def get_available_tools(self):
        if self._raise_on_get_tools:
            raise self._raise_on_get_tools
        return self._tools

    def execute_tool(self, tool_name, arguments, user_id=None):
        self.executed_calls.append((tool_name, arguments))
        result = self._execute_results.get(tool_name)
        if isinstance(result, Exception):
            raise result
        assert result is not None, f"Unexpected tool execution in test: {tool_name}"
        return result


SEARCH_TOOL = ToolDefinition(
    name="search_products", description="search the catalog", input_schema={"required": ["keyword"]}
)


def test_agent_runs_tool_call_then_final_response():
    tool_client = StubToolClient(
        tools=[SEARCH_TOOL],
        execute_results={"search_products": ToolCallResult(success=True, data=[{"id": 1, "name": "Nike Air"}])},
    )
    llm = ScriptedLLMClient(
        [
            json.dumps({"action": "TOOL_CALL", "tool_name": "search_products", "arguments": {"keyword": "nike"}}),
            json.dumps({"action": "FINAL_RESPONSE", "response": "Found Nike Air for you."}),
        ]
    )
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="find nike shoes", session_id="s1")

    assert state.status == AgentStatus.COMPLETED
    assert state.final_response == "Found Nike Air for you."
    assert tool_client.executed_calls == [("search_products", {"keyword": "nike"})]


def test_agent_stops_safely_at_max_iterations():
    tool_client = StubToolClient(
        tools=[SEARCH_TOOL], execute_results={"search_products": ToolCallResult(success=True, data=[])}
    )
    # The LLM keeps asking for the same tool call and never produces a final response.
    repeated_call = json.dumps(
        {"action": "TOOL_CALL", "tool_name": "search_products", "arguments": {"keyword": "nike"}}
    )
    llm = ScriptedLLMClient([repeated_call] * 10)
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=2)

    state = agent.run(user_request="find nike shoes")

    assert state.status == AgentStatus.FAILED
    assert state.error is not None
    assert state.iteration == 3  # fails on the iteration that exceeds the limit


def test_agent_observes_tool_failure_instead_of_assuming_success():
    tool_client = StubToolClient(
        tools=[SEARCH_TOOL],
        execute_results={
            "search_products": ToolCallResult(success=False, error_code="INTERNAL_ERROR", error_message="boom")
        },
    )
    llm = ScriptedLLMClient(
        [
            json.dumps({"action": "TOOL_CALL", "tool_name": "search_products", "arguments": {"keyword": "nike"}}),
            json.dumps({"action": "FINAL_RESPONSE", "response": "I couldn't search right now, please try again."}),
        ]
    )
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="find nike shoes")

    assert state.status == AgentStatus.COMPLETED
    assert state.tool_results[0].result.success is False
    assert state.tool_results[0].result.error_code == "INTERNAL_ERROR"


def test_agent_rejects_unknown_tool_and_recovers_on_next_iteration():
    tool_client = StubToolClient(tools=[SEARCH_TOOL])
    llm = ScriptedLLMClient(
        [
            json.dumps({"action": "TOOL_CALL", "tool_name": "not_a_real_tool", "arguments": {}}),
            json.dumps({"action": "FINAL_RESPONSE", "response": "I couldn't do that."}),
        ]
    )
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="do something unsupported")

    assert state.status == AgentStatus.COMPLETED
    assert tool_client.executed_calls == []  # ToolClient.execute_tool was never reached
    assert any("Tool call failed" in m.content for m in state.messages if m.role == "tool")


def test_agent_fails_safely_when_tool_service_unavailable_during_discovery():
    tool_client = StubToolClient(tools=[], raise_on_get_tools=ToolServiceUnavailableError("down"))
    llm = ScriptedLLMClient([])  # the LLM should never be called
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="find nike shoes")

    assert state.status == AgentStatus.FAILED
    assert state.error is not None


def test_agent_asks_user_for_clarification():
    tool_client = StubToolClient(tools=[SEARCH_TOOL])
    llm = ScriptedLLMClient(
        [json.dumps({"action": "ASK_USER", "clarification_question": "Which size do you need?"})]
    )
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="order me some shoes")

    assert state.status == AgentStatus.WAITING_FOR_USER
    assert state.final_response == "Which size do you need?"
