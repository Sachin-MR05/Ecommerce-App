"""
Python agent-level flow tests for order tools: create_order, get_orders.

Uses the StubToolClient + ScriptedLLMClient pattern from test_agent.py so that
no real HTTP, Java service, or LLM call is made.
"""
import json

from app.agent.agent_state import AgentStatus
from app.agent.merchant_agent import MerchantAgent
from app.llm.llm_client import LLMClient, LLMResponse
from app.tools.tool_schema import ToolCallResult, ToolDefinition


# ---------------------------------------------------------------------------
# Test doubles (same pattern as test_agent.py)
# ---------------------------------------------------------------------------

class ScriptedLLMClient(LLMClient):
    def __init__(self, responses):
        self._responses = list(responses)

    def generate(self, messages, tools=None) -> LLMResponse:
        assert self._responses, "No more scripted LLM responses"
        return LLMResponse(content=self._responses.pop(0))


class StubToolClient:
    def __init__(self, tools, execute_results=None):
        self._tools = tools
        self._execute_results = execute_results or {}
        self.executed_calls = []

    def get_available_tools(self):
        return self._tools

    def execute_tool(self, tool_name, arguments, user_id=None, context=None, request_id=None):
        self.executed_calls.append((tool_name, arguments))
        result = self._execute_results.get(tool_name)
        assert result is not None, f"Unexpected tool call: {tool_name}"
        return result


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

CREATE_ORDER_TOOL = ToolDefinition(
    name="create_order",
    description="Create an order from the current cart",
    input_schema={"type": "object", "properties": {}, "required": []},
)

GET_ORDERS_TOOL = ToolDefinition(
    name="get_orders",
    description="Retrieve order history or a single order",
    input_schema={"type": "object", "properties": {
        "orderId": {"type": "integer"},
    }, "required": []},
)

CHECKOUT_DATA = {
    "orderId": 100,
    "razorpayOrderId": "rzp_order_abc123",
    "amount": 29900,
    "currency": "INR",
    "keyId": "rzp_test_key",
}

ORDERS_LIST_DATA = [
    {
        "id": 1, "status": "PAID", "totalAmount": 299.00,
        "createdAt": "2026-08-24T10:00:00",
        "razorpayOrderId": "rzp_order_abc123", "razorpayPaymentId": "rzp_pay_xyz",
        "items": [{"productId": 10, "productName": "Nike Air", "price": 299.00, "quantity": 1}],
    },
    {
        "id": 2, "status": "CREATED", "totalAmount": 150.00,
        "createdAt": "2026-08-23T08:00:00",
        "razorpayOrderId": "rzp_order_def456", "razorpayPaymentId": None,
        "items": [{"productId": 20, "productName": "Puma Sprint", "price": 150.00, "quantity": 1}],
    },
]

SINGLE_ORDER_DATA = ORDERS_LIST_DATA[0]


# ---------------------------------------------------------------------------
# create_order tests
# ---------------------------------------------------------------------------

def test_agent_creates_order_from_cart():
    """
    Happy path: agent calls create_order and confirms to the user.
    """
    tool_client = StubToolClient(
        tools=[CREATE_ORDER_TOOL],
        execute_results={"create_order": ToolCallResult(success=True, data=CHECKOUT_DATA)},
    )
    llm = ScriptedLLMClient([
        json.dumps({"action": "TOOL_CALL", "tool_name": "create_order", "arguments": {}}),
        json.dumps({"action": "FINAL_RESPONSE",
                    "response": "Your order (id: 100) has been created. Total: ₹299.00"}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="place my order", user_id=42)

    assert state.status == AgentStatus.COMPLETED
    assert tool_client.executed_calls == [("create_order", {})]
    assert state.tool_results[0].result.success is True


def test_agent_handles_empty_cart_on_create_order():
    """
    If the cart is empty the agent observes the PAYMENT_ERROR and explains.
    """
    tool_client = StubToolClient(
        tools=[CREATE_ORDER_TOOL],
        execute_results={"create_order": ToolCallResult(
            success=False,
            error_code="PAYMENT_ERROR",
            error_message="Cannot checkout with an empty cart",
        )},
    )
    llm = ScriptedLLMClient([
        json.dumps({"action": "TOOL_CALL", "tool_name": "create_order", "arguments": {}}),
        json.dumps({"action": "FINAL_RESPONSE",
                    "response": "Your cart is empty. Please add items before placing an order."}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="place my order", user_id=42)

    assert state.status == AgentStatus.COMPLETED
    assert state.tool_results[0].result.success is False
    assert state.tool_results[0].result.error_code == "PAYMENT_ERROR"
    assert "empty" in state.final_response.lower() or "cart" in state.final_response.lower()


def test_agent_does_not_confirm_order_on_internal_error():
    """
    An INTERNAL_ERROR from create_order must never be presented as a
    successful order placement.
    """
    tool_client = StubToolClient(
        tools=[CREATE_ORDER_TOOL],
        execute_results={"create_order": ToolCallResult(
            success=False,
            error_code="INTERNAL_ERROR",
            error_message="Something went wrong while executing tool 'create_order'",
        )},
    )
    llm = ScriptedLLMClient([
        json.dumps({"action": "TOOL_CALL", "tool_name": "create_order", "arguments": {}}),
        json.dumps({"action": "FINAL_RESPONSE",
                    "response": "I encountered an error placing your order. Please try again."}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="place my order", user_id=42)

    assert state.status == AgentStatus.COMPLETED
    # The final response must NOT claim the order succeeded
    lower = state.final_response.lower()
    assert "order" not in lower.replace("order.", "").replace("order!", "") or "error" in lower or "try again" in lower


# ---------------------------------------------------------------------------
# get_orders tests
# ---------------------------------------------------------------------------

def test_agent_retrieves_full_order_history():
    """
    Agent calls get_orders with no orderId and summarises the history.
    """
    tool_client = StubToolClient(
        tools=[GET_ORDERS_TOOL],
        execute_results={"get_orders": ToolCallResult(success=True, data=ORDERS_LIST_DATA)},
    )
    llm = ScriptedLLMClient([
        json.dumps({"action": "TOOL_CALL", "tool_name": "get_orders", "arguments": {}}),
        json.dumps({"action": "FINAL_RESPONSE",
                    "response": "You have 2 orders: order 1 (PAID, ₹299) and order 2 (CREATED, ₹150)."}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="show me my order history", user_id=42)

    assert state.status == AgentStatus.COMPLETED
    assert tool_client.executed_calls == [("get_orders", {})]
    assert state.tool_results[0].result.success is True


def test_agent_retrieves_single_order_by_id():
    """
    Agent calls get_orders with an orderId to fetch a specific order.
    """
    tool_client = StubToolClient(
        tools=[GET_ORDERS_TOOL],
        execute_results={"get_orders": ToolCallResult(success=True, data=SINGLE_ORDER_DATA)},
    )
    llm = ScriptedLLMClient([
        json.dumps({"action": "TOOL_CALL", "tool_name": "get_orders", "arguments": {"orderId": 1}}),
        json.dumps({"action": "FINAL_RESPONSE",
                    "response": "Order 1: PAID, ₹299.00, Nike Air x1."}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="what's the status of order 1?", user_id=42)

    assert state.status == AgentStatus.COMPLETED
    assert tool_client.executed_calls == [("get_orders", {"orderId": 1})]


def test_agent_handles_order_not_found():
    """
    NOT_FOUND from get_orders is communicated honestly to the user.
    """
    tool_client = StubToolClient(
        tools=[GET_ORDERS_TOOL],
        execute_results={"get_orders": ToolCallResult(
            success=False,
            error_code="NOT_FOUND",
            error_message="Order not found with id: 999",
        )},
    )
    llm = ScriptedLLMClient([
        json.dumps({"action": "TOOL_CALL", "tool_name": "get_orders", "arguments": {"orderId": 999}}),
        json.dumps({"action": "FINAL_RESPONSE",
                    "response": "I couldn't find an order with id 999 associated with your account."}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="show me order 999", user_id=42)

    assert state.status == AgentStatus.COMPLETED
    assert state.tool_results[0].result.error_code == "NOT_FOUND"
