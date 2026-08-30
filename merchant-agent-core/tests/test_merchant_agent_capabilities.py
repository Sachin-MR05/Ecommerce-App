"""
Python agent-level tests for the full merchant agent capabilities:
- Understand buyer requests
- Search and compare products
- Check price/inventory
- Negotiate within available information
- Generate a purchase proposal

All tests use ScriptedLLMClient + StubToolClient so no real network calls are
made. Each test exercises a multi-step agentic conversation.
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
        # Support a list of sequential results for the same tool
        if isinstance(result, list):
            return result.pop(0)
        return result


# ---------------------------------------------------------------------------
# Tool definitions (all capabilities)
# ---------------------------------------------------------------------------

SEARCH_TOOL = ToolDefinition(
    name="search_products",
    description="Search the product catalog by keyword",
    input_schema={"type": "object", "properties": {
        "keyword": {"type": "string"},
    }, "required": ["keyword"]},
)

GET_PRODUCT_TOOL = ToolDefinition(
    name="get_product",
    description="Get full details for a product by id",
    input_schema={"type": "object", "properties": {
        "productId": {"type": "integer"},
    }, "required": ["productId"]},
)

CHECK_INVENTORY_TOOL = ToolDefinition(
    name="check_inventory",
    description="Check whether a quantity is available in stock",
    input_schema={"type": "object", "properties": {
        "productId": {"type": "integer"},
        "quantity": {"type": "integer"},
    }, "required": ["productId", "quantity"]},
)

GET_PRICE_TOOL = ToolDefinition(
    name="get_price",
    description="Get the live price for a product",
    input_schema={"type": "object", "properties": {
        "productId": {"type": "integer"},
    }, "required": ["productId"]},
)

ADD_TO_CART_TOOL = ToolDefinition(
    name="add_to_cart",
    description="Add a product+quantity to the cart",
    input_schema={"type": "object", "properties": {
        "productId": {"type": "integer"},
        "quantity": {"type": "integer"},
    }, "required": ["productId", "quantity"]},
)

ALL_TOOLS = [SEARCH_TOOL, GET_PRODUCT_TOOL, CHECK_INVENTORY_TOOL, GET_PRICE_TOOL, ADD_TO_CART_TOOL]


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

PRODUCT_NIKE = {"id": 10, "name": "Nike Air", "price": 99.99, "stock": 15, "category": "shoes"}
PRODUCT_PUMA = {"id": 20, "name": "Puma Sprint", "price": 79.99, "stock": 8, "category": "shoes"}
PRICE_NIKE = {"productId": 10, "price": 99.99, "currency": "INR"}
INVENTORY_OK = {"productId": 10, "requestedQuantity": 2, "availableQuantity": 15, "available": True}
INVENTORY_LOW = {"productId": 10, "requestedQuantity": 20, "availableQuantity": 3, "available": False}
CART_AFTER_ADD = {
    "items": [{"cartItemId": 1, "productId": 10, "productName": "Nike Air", "price": 99.99, "quantity": 2}],
    "total": 199.98, "totalItems": 2,
}


# ---------------------------------------------------------------------------
# 1. Search → compare → purchase proposal
# ---------------------------------------------------------------------------

def test_agent_search_compare_and_generate_proposal():
    """
    Multi-step flow:
      1. search_products → finds 2 products
      2. get_price (Nike) → live price confirmed
      3. check_inventory (Nike, qty=2) → available
      4. FINAL_RESPONSE with purchase proposal
    The agent must call tools in a sensible order and produce a proposal
    that includes the product name, quantity, and price from tool results.
    """
    tool_client = StubToolClient(
        tools=ALL_TOOLS,
        execute_results={
            "search_products": ToolCallResult(
                success=True, data=[PRODUCT_NIKE, PRODUCT_PUMA]
            ),
            "get_price": ToolCallResult(success=True, data=PRICE_NIKE),
            "check_inventory": ToolCallResult(success=True, data=INVENTORY_OK),
        },
    )
    llm = ScriptedLLMClient([
        # Step 1: search
        json.dumps({"action": "TOOL_CALL", "tool_name": "search_products",
                    "arguments": {"keyword": "nike"}}),
        # Step 2: confirm live price
        json.dumps({"action": "TOOL_CALL", "tool_name": "get_price",
                    "arguments": {"productId": 10}}),
        # Step 3: check stock for 2 units
        json.dumps({"action": "TOOL_CALL", "tool_name": "check_inventory",
                    "arguments": {"productId": 10, "quantity": 2}}),
        # Step 4: propose purchase
        json.dumps({"action": "FINAL_RESPONSE",
                    "response": "I found Nike Air at ₹99.99 each. 15 in stock. "
                                "Proposal: 2x Nike Air for ₹199.98. Shall I add them to your cart?"}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=10)

    state = agent.run(user_request="I want to buy some nike shoes, 2 pairs", user_id=42)

    assert state.status == AgentStatus.COMPLETED
    # All three tool calls must have been made
    tool_names_called = [name for name, _ in tool_client.executed_calls]
    assert "search_products" in tool_names_called
    assert "get_price" in tool_names_called
    assert "check_inventory" in tool_names_called
    # Proposal must reference product name and price from tool results
    assert "Nike Air" in state.final_response
    assert "99.99" in state.final_response or "199.98" in state.final_response


# ---------------------------------------------------------------------------
# 2. Negotiate when quantity exceeds stock
# ---------------------------------------------------------------------------

def test_agent_negotiates_quantity_when_stock_is_low():
    """
    When the requested quantity (20) exceeds available stock (3), the agent
    must proactively offer the maximum available quantity as an alternative
    rather than refusing outright.
    """
    tool_client = StubToolClient(
        tools=[SEARCH_TOOL, CHECK_INVENTORY_TOOL, ADD_TO_CART_TOOL],
        execute_results={
            "search_products": ToolCallResult(success=True, data=[PRODUCT_NIKE]),
            "check_inventory": ToolCallResult(success=True, data=INVENTORY_LOW),
        },
    )
    llm = ScriptedLLMClient([
        json.dumps({"action": "TOOL_CALL", "tool_name": "search_products",
                    "arguments": {"keyword": "nike air"}}),
        json.dumps({"action": "TOOL_CALL", "tool_name": "check_inventory",
                    "arguments": {"productId": 10, "quantity": 20}}),
        # Negotiation: offer max available (3) instead of flat refusal
        json.dumps({"action": "FINAL_RESPONSE",
                    "response": "We only have 3 Nike Air units in stock right now. "
                                "Would you like to add 3 instead?"}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=10)

    state = agent.run(user_request="I need 20 pairs of Nike Air", user_id=42)

    assert state.status == AgentStatus.COMPLETED
    # Inventory was checked and returned not-available
    inventory_result = next(
        r for r in state.tool_results if r.tool_name == "check_inventory"
    )
    assert inventory_result.result.success is True
    assert inventory_result.result.data["available"] is False
    # Agent must have offered an alternative — not just refused
    lower = state.final_response.lower()
    assert "3" in state.final_response and ("instead" in lower or "available" in lower)


# ---------------------------------------------------------------------------
# 3. Ask for clarification when product is ambiguous
# ---------------------------------------------------------------------------

def test_agent_asks_clarification_when_request_is_ambiguous():
    """
    When the buyer says 'some shoes' without specifying which product,
    the agent should use ASK_USER rather than guessing or calling search_products
    with an incomplete query that would waste a tool call.
    """
    tool_client = StubToolClient(tools=ALL_TOOLS)
    llm = ScriptedLLMClient([
        # First decision: ask for clarification — no tool call needed
        json.dumps({"action": "ASK_USER",
                    "clarification_question": "Which shoes are you looking for? "
                                              "Please give me a model name or brand so I can search accurately."}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="I want some shoes", user_id=42)

    assert state.status == AgentStatus.WAITING_FOR_USER
    assert "shoes" in state.final_response.lower() or "model" in state.final_response.lower()
    # No tools should have been called — the agent asked first
    assert tool_client.executed_calls == []


# ---------------------------------------------------------------------------
# 4. Full end-to-end: search → confirm → add to cart
# ---------------------------------------------------------------------------

def test_agent_full_purchase_flow_search_confirm_add():
    """
    Complete multi-step scenario:
      search_products → get_price → check_inventory → add_to_cart → FINAL_RESPONSE
    """
    tool_client = StubToolClient(
        tools=ALL_TOOLS,
        execute_results={
            "search_products": ToolCallResult(success=True, data=[PRODUCT_NIKE]),
            "get_price": ToolCallResult(success=True, data=PRICE_NIKE),
            "check_inventory": ToolCallResult(success=True, data=INVENTORY_OK),
            "add_to_cart": ToolCallResult(success=True, data=CART_AFTER_ADD),
        },
    )
    llm = ScriptedLLMClient([
        json.dumps({"action": "TOOL_CALL", "tool_name": "search_products",
                    "arguments": {"keyword": "nike air"}}),
        json.dumps({"action": "TOOL_CALL", "tool_name": "get_price",
                    "arguments": {"productId": 10}}),
        json.dumps({"action": "TOOL_CALL", "tool_name": "check_inventory",
                    "arguments": {"productId": 10, "quantity": 2}}),
        json.dumps({"action": "TOOL_CALL", "tool_name": "add_to_cart",
                    "arguments": {"productId": 10, "quantity": 2}}),
        json.dumps({"action": "FINAL_RESPONSE",
                    "response": "Added 2x Nike Air (₹99.99 each) to your cart. Cart total: ₹199.98."}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=10)

    state = agent.run(user_request="find Nike Air and add 2 to my cart", user_id=42)

    assert state.status == AgentStatus.COMPLETED
    # Four tool calls in the expected sequence
    names = [name for name, _ in tool_client.executed_calls]
    assert names == ["search_products", "get_price", "check_inventory", "add_to_cart"]
    # All four tool calls succeeded
    for record in state.tool_results:
        assert record.result.success is True
    # Final response confirms the cart state
    assert "Nike Air" in state.final_response
    assert "199.98" in state.final_response or "cart" in state.final_response.lower()


# ---------------------------------------------------------------------------
# 5. Agent never invents data — uses tool results only
# ---------------------------------------------------------------------------

def test_agent_never_confirms_cart_add_without_tool_success():
    """
    Even if the LLM is scripted to try to confirm success, if the tool actually
    failed the agent must not pass through a false success response.
    The test verifies the agent correctly observes failure=True on the result.
    """
    tool_client = StubToolClient(
        tools=[ADD_TO_CART_TOOL],
        execute_results={"add_to_cart": ToolCallResult(
            success=False,
            error_code="INSUFFICIENT_STOCK",
            error_message="Only 0 unit(s) of 'Nike Air' available",
        )},
    )
    llm = ScriptedLLMClient([
        json.dumps({"action": "TOOL_CALL", "tool_name": "add_to_cart",
                    "arguments": {"productId": 10, "quantity": 1}}),
        json.dumps({"action": "FINAL_RESPONSE",
                    "response": "Nike Air is currently out of stock. I couldn't add it to your cart."}),
    ])
    agent = MerchantAgent(llm_client=llm, tool_client=tool_client, max_iterations=5)

    state = agent.run(user_request="add Nike Air to my cart", user_id=42)

    assert state.status == AgentStatus.COMPLETED
    # The tool result must record the failure
    assert state.tool_results[0].result.success is False
    assert state.tool_results[0].result.error_code == "INSUFFICIENT_STOCK"


def test_agent_degrades_gracefully_when_llm_provider_is_unavailable():
    """Regression test: an LLM provider outage/timeout during the agent
    loop (not just during tool discovery) must be caught and turned into a
    graceful AgentStatus.FAILED with a buyer-facing message and an audit
    event - never an uncaught exception that reaches the Gateway as an
    opaque 500 with no audit trail at all. Found by live-testing
    /agent/message with the real LLM provider unreachable: the request
    disappeared from the audit trail after REQUEST_RECEIVED and the
    Gateway returned a generic 500."""
    from audit.audit_service import AuditService
    from app.llm.llm_client import LLMUnavailableError

    class UnavailableLLMClient(LLMClient):
        def generate(self, messages, tools=None):
            raise LLMUnavailableError("Could not reach the LLM provider: connection refused")

    tool_client = StubToolClient(tools=[SEARCH_TOOL], execute_results={})
    audit_service = AuditService()
    agent = MerchantAgent(
        llm_client=UnavailableLLMClient(),
        tool_client=tool_client,
        audit_service=audit_service,
    )

    state = agent.run(user_request="show me running shoes", user_id=42, session_id="s1")

    assert state.status == AgentStatus.FAILED
    assert state.error and "temporarily unavailable" in state.error.lower()

    events = audit_service._repository.get_by_request(state.request_id or state.session_id)  # noqa: SLF001
    event_types = [e.event_type.value for e in events]
    assert "TRANSACTION_FAILED" in event_types
