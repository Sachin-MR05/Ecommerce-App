"""
Python agent-level flow tests for cart tools: add_to_cart, update_cart, remove_from_cart.

Uses the StubToolClient + ScriptedLLMClient pattern from test_agent.py so that
no real HTTP, Java service, or LLM call is made. Every test exercises the full
MerchantAgent → AgentLoop → Planner → Executor → ToolClient path.
"""
import json

from app.agent.agent_state import AgentStatus
from app.agent.merchant_agent import MerchantAgent
from app.llm.llm_client import LLMClient, LLMResponse
from app.tools.tool_schema import ToolCallResult, ToolDefinition


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class ScriptedLLMClient(LLMClient):
    """Returns pre-scripted JSON responses in order — no real LLM call is made."""

    def __init__(self, responses):
        self._responses = list(responses)

    def generate(self, messages, tools=None) -> LLMResponse:
        assert self._responses, "No more scripted LLM responses"
        return LLMResponse(content=self._responses.pop(0))


class StubToolClient:
    """Duck-types ToolClient (get_available_tools / execute_tool) without HTTP."""

    def __init__(self, tools, execute_results=None, raise_on_get_tools=None):
        self._tools = tools
        self._execute_results = execute_results or {}
        self._raise_on_get_tools = raise_on_get_tools
        self.executed_calls = []

    def get_available_tools(self):
        if self._raise_on_get_tools:
            raise self._raise_on_get_tools
        return self._tools

    def execute_tool(self, tool_name, arguments, user_id=None, context=None, request_id=None):
        self.executed_calls.append((tool_name, arguments))
        result = self._execute_results.get(tool_name)
        if isinstance(result, Exception):
            raise result
        assert result is not None, f"Unexpected tool call in test: {tool_name}"
        return result


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

ADD_TO_CART_TOOL = ToolDefinition(
    name="add_to_cart",
    description="Add a product+quantity to the cart",
    input_schema={"type": "object", "properties": {
        "productId": {"type": "integer"},
        "quantity": {"type": "integer"},
    }, "required": ["productId", "quantity"]},
)

UPDATE_CART_TOOL = ToolDefinition(
    name="update_cart",
    description="Set an existing cart item to an exact quantity",
    input_schema={"type": "object", "properties": {
        "cartItemId": {"type": "integer"},
        "quantity": {"type": "integer"},
    }, "required": ["cartItemId", "quantity"]},
)

REMOVE_CART_TOOL = ToolDefinition(
    name="remove_from_cart",
    description="Remove a single cart line item entirely",
    input_schema={"type": "object", "properties": {
        "cartItemId": {"type": "integer"},
    }, "required": ["cartItemId"]},
)

CART_SUCCESS_DATA = {
    "items": [{"cartItemId": 1, "productId": 10, "productName": "Nike Air", "price": 99.99, "quantity": 2}],
    "total": 199.98,
    "totalItems": 2,
}

EMPTY_CART_DATA = {"items": [], "total": 0.0, "totalItems": 0}


# ---------------------------------------------------------------------------
# add_to_cart tests
# ---------------------------------------------------------------------------

def test_agent_adds_to_cart_then_confirms():
    """
    Happy path: agent calls add_to_cart, sees success, gives a final response.
    """
    tool_client = StubToolClient(
        tools=[ADD_TO_CART_TOOL],
        execute_results={"add_to_cart": ToolCallResult(success=True, data=CART_SUCCESS_DATA)},
    )
    llm = ScriptedLLMClient([
        json.dumps({"action": "TOOL_CALL", "tool_name": "add_to_cart",
                    "arguments": {"productId": 10, "quantity": 2}}),
        json.dumps({"action": "FINAL_RESPONSE",
                    "response": "Added 2x Nike Air to your cart. Total: $199.98"}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="add 2 Nike Air shoes to my cart", user_id=42)

    assert state.status == AgentStatus.COMPLETED
    assert "Nike Air" in state.final_response or "$" in state.final_response
    assert tool_client.executed_calls == [("add_to_cart", {"productId": 10, "quantity": 2})]


def test_agent_handles_insufficient_stock_after_add_to_cart():
    """
    When add_to_cart returns INSUFFICIENT_STOCK the agent observes the failure
    and explains it to the user rather than ignoring it.
    """
    tool_client = StubToolClient(
        tools=[ADD_TO_CART_TOOL],
        execute_results={"add_to_cart": ToolCallResult(
            success=False,
            error_code="INSUFFICIENT_STOCK",
            error_message="Only 1 unit(s) of 'Nike Air' available",
        )},
    )
    llm = ScriptedLLMClient([
        json.dumps({"action": "TOOL_CALL", "tool_name": "add_to_cart",
                    "arguments": {"productId": 10, "quantity": 50}}),
        json.dumps({"action": "FINAL_RESPONSE",
                    "response": "Sorry, only 1 unit of Nike Air is available right now."}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="add 50 Nike Air shoes", user_id=42)

    assert state.status == AgentStatus.COMPLETED
    # The agent must have observed the failure (not succeed=True on the tool result)
    assert state.tool_results[0].result.success is False
    assert state.tool_results[0].result.error_code == "INSUFFICIENT_STOCK"
    # Final response acknowledges the stock issue
    assert "1" in state.final_response or "available" in state.final_response.lower()


def test_agent_reports_add_to_cart_not_found_error():
    """
    If the product doesn't exist the agent surfaces a NOT_FOUND explanation.
    """
    tool_client = StubToolClient(
        tools=[ADD_TO_CART_TOOL],
        execute_results={"add_to_cart": ToolCallResult(
            success=False,
            error_code="NOT_FOUND",
            error_message="Product not found with id: 999",
        )},
    )
    llm = ScriptedLLMClient([
        json.dumps({"action": "TOOL_CALL", "tool_name": "add_to_cart",
                    "arguments": {"productId": 999, "quantity": 1}}),
        json.dumps({"action": "FINAL_RESPONSE",
                    "response": "I couldn't find that product. Please check the product id."}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="add product 999 to cart", user_id=42)

    assert state.status == AgentStatus.COMPLETED
    assert state.tool_results[0].result.error_code == "NOT_FOUND"


# ---------------------------------------------------------------------------
# update_cart tests
# ---------------------------------------------------------------------------

def test_agent_updates_cart_quantity():
    """
    Agent calls update_cart with a new quantity and confirms the change.
    """
    updated_cart = {
        "items": [{"cartItemId": 1, "productId": 10, "productName": "Nike Air", "price": 99.99, "quantity": 5}],
        "total": 499.95,
        "totalItems": 5,
    }
    tool_client = StubToolClient(
        tools=[UPDATE_CART_TOOL],
        execute_results={"update_cart": ToolCallResult(success=True, data=updated_cart)},
    )
    llm = ScriptedLLMClient([
        json.dumps({"action": "TOOL_CALL", "tool_name": "update_cart",
                    "arguments": {"cartItemId": 1, "quantity": 5}}),
        json.dumps({"action": "FINAL_RESPONSE",
                    "response": "Updated your Nike Air quantity to 5. New total: $499.95"}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="change the Nike Air quantity to 5", user_id=42)

    assert state.status == AgentStatus.COMPLETED
    assert tool_client.executed_calls == [("update_cart", {"cartItemId": 1, "quantity": 5})]
    assert state.tool_results[0].result.success is True


def test_agent_handles_update_cart_not_found():
    """
    If the cart item doesn't belong to the user the agent explains the failure.
    """
    tool_client = StubToolClient(
        tools=[UPDATE_CART_TOOL],
        execute_results={"update_cart": ToolCallResult(
            success=False,
            error_code="NOT_FOUND",
            error_message="Cart item not found with id: 99",
        )},
    )
    llm = ScriptedLLMClient([
        json.dumps({"action": "TOOL_CALL", "tool_name": "update_cart",
                    "arguments": {"cartItemId": 99, "quantity": 3}}),
        json.dumps({"action": "FINAL_RESPONSE",
                    "response": "I couldn't find that cart item. Please check and try again."}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="update cart item 99 to quantity 3", user_id=42)

    assert state.status == AgentStatus.COMPLETED
    assert state.tool_results[0].result.error_code == "NOT_FOUND"


# ---------------------------------------------------------------------------
# remove_from_cart tests
# ---------------------------------------------------------------------------

def test_agent_removes_item_from_cart():
    """
    Agent calls remove_from_cart and confirms the item was removed.
    """
    tool_client = StubToolClient(
        tools=[REMOVE_CART_TOOL],
        execute_results={"remove_from_cart": ToolCallResult(success=True, data=EMPTY_CART_DATA)},
    )
    llm = ScriptedLLMClient([
        json.dumps({"action": "TOOL_CALL", "tool_name": "remove_from_cart",
                    "arguments": {"cartItemId": 1}}),
        json.dumps({"action": "FINAL_RESPONSE",
                    "response": "Removed the item from your cart. Your cart is now empty."}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="remove cart item 1", user_id=42)

    assert state.status == AgentStatus.COMPLETED
    assert tool_client.executed_calls == [("remove_from_cart", {"cartItemId": 1})]
    assert state.tool_results[0].result.success is True


def test_agent_handles_remove_cart_not_found():
    """
    If the cart item doesn't exist the agent surfaces the failure clearly.
    """
    tool_client = StubToolClient(
        tools=[REMOVE_CART_TOOL],
        execute_results={"remove_from_cart": ToolCallResult(
            success=False,
            error_code="NOT_FOUND",
            error_message="Cart item not found with id: 77",
        )},
    )
    llm = ScriptedLLMClient([
        json.dumps({"action": "TOOL_CALL", "tool_name": "remove_from_cart",
                    "arguments": {"cartItemId": 77}}),
        json.dumps({"action": "FINAL_RESPONSE",
                    "response": "That item wasn't found in your cart. Nothing was removed."}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="remove cart item 77", user_id=42)

    assert state.status == AgentStatus.COMPLETED
    assert state.tool_results[0].result.error_code == "NOT_FOUND"
