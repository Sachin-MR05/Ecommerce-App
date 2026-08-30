"""
Standalone MOCK of the Java Tool Layer, for exercising the real agent
reasoning + tool-calling loop (Planner -> Executor -> ToolClient) end to
end, without the real Java service.

This is a DEV/TEST TOOL ONLY - it is not part of merchant-agent-core's
application code, is not imported by anything else, and should never be
pointed at from a real deployment. It implements just enough of the wire
contract (see contracts/README.md, app/tools/tool_schema.py) to let a real
LLM provider actually call tools and get plausible-looking data back:

  GET  /tools                          -> {"tools": [ToolDefinition, ...]}
  POST /tools/{toolName}/execute       -> ToolResponse (contracts.tool_response)

Implements every tool currently listed as real in
app/tools/tool_schema.py's KNOWN_TOOL_NAMES comment: search_products,
get_product, check_inventory, get_price, add_to_cart, update_cart,
remove_from_cart, create_order, get_orders, verify_payment.

Run it:
    pip install fastapi uvicorn
    uvicorn tools_mock_server:app --port 9000

Then point merchant-agent-core at it:
    TOOL_SERVICE_URL=http://localhost:9000 uvicorn main:app --port 8000
"""

from __future__ import annotations

import itertools
import random
import time
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Mock Java Tool Layer (dev/test only)")

# ---------------------------------------------------------------------------
# Fake in-memory catalog / cart / order state - resets on restart. Enough to
# make a multi-turn conversation (search -> add to cart -> checkout) behave
# plausibly, not a real inventory system.
# ---------------------------------------------------------------------------
_PRODUCTS: dict[str, dict[str, Any]] = {
    "P1001": {"id": "P1001", "name": "Trailblazer Running Shoes", "category": "footwear", "price": 1799, "currency": "INR", "stock": 12},
    "P1002": {"id": "P1002", "name": "Everyday Cotton T-Shirt (Blue, M)", "category": "apparel", "price": 499, "currency": "INR", "stock": 40},
    "P1003": {"id": "P1003", "name": "AirFlex Sports Socks (Pack of 3)", "category": "apparel", "price": 299, "currency": "INR", "stock": 0},
    "P1004": {"id": "P1004", "name": "Wireless Earbuds X200", "category": "electronics", "price": 2499, "currency": "INR", "stock": 8},
}

_carts: dict[str, dict[str, int]] = {}  # userId(str) -> {productId: quantity}
_orders: dict[int, dict[str, Any]] = {}
_order_id_seq = itertools.count(9001)


def _user_key(context: dict[str, Any]) -> str:
    return str(context.get("userId", "anonymous"))


def _ok(request_id: str, result: Any) -> dict:
    return {"requestId": request_id, "success": True, "result": result, "error": None}


def _err(request_id: str, code: str, message: str, error_type: str = "TOOL_EXECUTION_ERROR", details: dict | None = None) -> dict:
    return {
        "requestId": request_id,
        "success": False,
        "result": None,
        "error": {"code": code, "message": message, "type": error_type, "details": details or {}},
    }


# ---------------------------------------------------------------------------
# GET /tools - tool discovery
# ---------------------------------------------------------------------------

_TOOL_DEFINITIONS = [
    {
        "name": "search_products",
        "description": "Search the product catalog by free-text query, optional category, and optional max price.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "category": {"type": "string"},
                "maxPrice": {"type": "number"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_product",
        "description": "Get full details for a single product by id.",
        "inputSchema": {"type": "object", "properties": {"productId": {"type": "string"}}, "required": ["productId"]},
    },
    {
        "name": "check_inventory",
        "description": "Check whether a given quantity of a product is currently available.",
        "inputSchema": {
            "type": "object",
            "properties": {"productId": {"type": "string"}, "quantity": {"type": "integer"}},
            "required": ["productId", "quantity"],
        },
    },
    {
        "name": "get_price",
        "description": "Get the current price for a product.",
        "inputSchema": {"type": "object", "properties": {"productId": {"type": "string"}}, "required": ["productId"]},
    },
    {
        "name": "add_to_cart",
        "description": "Add a quantity of a product to the current user's cart.",
        "inputSchema": {
            "type": "object",
            "properties": {"productId": {"type": "string"}, "quantity": {"type": "integer"}},
            "required": ["productId", "quantity"],
        },
    },
    {
        "name": "update_cart",
        "description": "Update the quantity of a product already in the current user's cart.",
        "inputSchema": {
            "type": "object",
            "properties": {"productId": {"type": "string"}, "quantity": {"type": "integer"}},
            "required": ["productId", "quantity"],
        },
    },
    {
        "name": "remove_from_cart",
        "description": "Remove a product from the current user's cart.",
        "inputSchema": {"type": "object", "properties": {"productId": {"type": "string"}}, "required": ["productId"]},
    },
    {
        "name": "create_order",
        "description": "Create an order (and a payment provider order reference) from the current user's cart.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_orders",
        "description": "Look up an order by id.",
        "inputSchema": {"type": "object", "properties": {"orderId": {"type": "integer"}}, "required": ["orderId"]},
    },
    {
        "name": "verify_payment",
        "description": "Verify a completed payment against the payment provider and confirm the order.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "razorpayOrderId": {"type": "string"},
                "razorpayPaymentId": {"type": "string"},
                "razorpaySignature": {"type": "string"},
            },
            "required": ["razorpayOrderId", "razorpayPaymentId", "razorpaySignature"],
        },
    },
]


@app.get("/tools")
def get_tools() -> dict:
    return {"tools": _TOOL_DEFINITIONS}


# ---------------------------------------------------------------------------
# POST /tools/{toolName}/execute - tool execution
# ---------------------------------------------------------------------------

@app.post("/tools/{tool_name}/execute")
def execute_tool(tool_name: str, body: dict) -> JSONResponse:
    request_id = body.get("requestId", "unknown")
    arguments = body.get("arguments", {}) or {}
    context = body.get("context", {}) or {}

    # Simulate a little real network/processing latency so
    # /monitoring/metrics -> performance.api_latency_ms shows something
    # non-instant, like a real backend would.
    time.sleep(random.uniform(0.02, 0.12))

    handler = _HANDLERS.get(tool_name)
    if handler is None:
        return JSONResponse(_err(request_id, "TOOL_NOT_FOUND", f"Unknown tool '{tool_name}'", "NOT_FOUND"))

    return JSONResponse(handler(request_id, arguments, context))


def _search_products(request_id: str, args: dict, context: dict) -> dict:
    query = str(args.get("query", "")).lower()
    category = args.get("category")
    max_price = args.get("maxPrice")

    results = []
    for product in _PRODUCTS.values():
        if query and query not in product["name"].lower() and query not in product["category"]:
            continue
        if category and product["category"] != category:
            continue
        if max_price is not None and product["price"] > max_price:
            continue
        results.append(product)

    return _ok(request_id, {"products": results})


def _get_product(request_id: str, args: dict, context: dict) -> dict:
    product = _PRODUCTS.get(args.get("productId"))
    if product is None:
        return _err(request_id, "PRODUCT_NOT_FOUND", f"No product with id {args.get('productId')}", "NOT_FOUND")
    return _ok(request_id, product)


def _check_inventory(request_id: str, args: dict, context: dict) -> dict:
    product = _PRODUCTS.get(args.get("productId"))
    if product is None:
        return _err(request_id, "PRODUCT_NOT_FOUND", f"No product with id {args.get('productId')}", "NOT_FOUND")
    quantity = int(args.get("quantity", 1))
    available = product["stock"] >= quantity
    return _ok(
        request_id,
        {
            "productId": product["id"],
            "requestedQuantity": quantity,
            "availableQuantity": product["stock"],
            "available": available,
        },
    )


def _get_price(request_id: str, args: dict, context: dict) -> dict:
    product = _PRODUCTS.get(args.get("productId"))
    if product is None:
        return _err(request_id, "PRODUCT_NOT_FOUND", f"No product with id {args.get('productId')}", "NOT_FOUND")
    return _ok(request_id, {"productId": product["id"], "price": product["price"], "currency": product["currency"]})


def _add_to_cart(request_id: str, args: dict, context: dict) -> dict:
    product = _PRODUCTS.get(args.get("productId"))
    if product is None:
        return _err(request_id, "PRODUCT_NOT_FOUND", f"No product with id {args.get('productId')}", "NOT_FOUND")
    quantity = int(args.get("quantity", 1))
    if product["stock"] < quantity:
        return _err(
            request_id,
            "INSUFFICIENT_STOCK",
            f"Only {product['stock']} unit(s) available",
            "INVENTORY_UNAVAILABLE",
        )
    cart = _carts.setdefault(_user_key(context), {})
    cart[product["id"]] = cart.get(product["id"], 0) + quantity
    return _ok(request_id, {"cart": cart})


def _update_cart(request_id: str, args: dict, context: dict) -> dict:
    cart = _carts.setdefault(_user_key(context), {})
    product_id = args.get("productId")
    if product_id not in cart:
        return _err(request_id, "CART_ITEM_NOT_FOUND", f"{product_id} is not in the cart", "NOT_FOUND")
    cart[product_id] = int(args.get("quantity", 1))
    return _ok(request_id, {"cart": cart})


def _remove_from_cart(request_id: str, args: dict, context: dict) -> dict:
    cart = _carts.setdefault(_user_key(context), {})
    cart.pop(args.get("productId"), None)
    return _ok(request_id, {"cart": cart})


def _create_order(request_id: str, args: dict, context: dict) -> dict:
    cart = _carts.get(_user_key(context), {})
    if not cart:
        return _err(request_id, "CART_EMPTY", "Cannot create an order from an empty cart", "VALIDATION_ERROR")

    total = sum(_PRODUCTS[pid]["price"] * qty for pid, qty in cart.items() if pid in _PRODUCTS)
    order_id = next(_order_id_seq)
    provider_order_reference = f"order_mock_{order_id}"
    _orders[order_id] = {
        "orderId": order_id,
        "userId": context.get("userId"),
        "items": [{"productId": pid, "quantity": qty} for pid, qty in cart.items()],
        "amount": total,
        "currency": "INR",
        "status": "PAYMENT_PENDING",
        "providerOrderReference": provider_order_reference,
        "providerKeyId": "rzp_test_mock_key",
    }
    return _ok(
        request_id,
        {
            "orderId": order_id,
            "amount": total,
            "currency": "INR",
            "providerOrderReference": provider_order_reference,
            "providerKeyId": "rzp_test_mock_key",
        },
    )


def _get_orders(request_id: str, args: dict, context: dict) -> dict:
    order_id = args.get("orderId")
    order = _orders.get(order_id)
    if order is None:
        return _err(request_id, "ORDER_NOT_FOUND", f"No order with id {order_id}", "NOT_FOUND")
    return _ok(request_id, order)


def _verify_payment(request_id: str, args: dict, context: dict) -> dict:
    provider_order_reference = args.get("razorpayOrderId")
    order = next((o for o in _orders.values() if o["providerOrderReference"] == provider_order_reference), None)
    if order is None:
        return _err(request_id, "ORDER_NOT_FOUND", f"No order for {provider_order_reference}", "NOT_FOUND")
    order["status"] = "PAID"
    return _ok(
        request_id,
        {
            "orderId": order["orderId"],
            "paymentId": args.get("razorpayPaymentId", "pay_mock_1"),
            "status": "PAID",
        },
    )


_HANDLERS = {
    "search_products": _search_products,
    "get_product": _get_product,
    "check_inventory": _check_inventory,
    "get_price": _get_price,
    "add_to_cart": _add_to_cart,
    "update_cart": _update_cart,
    "remove_from_cart": _remove_from_cart,
    "create_order": _create_order,
    "get_orders": _get_orders,
    "verify_payment": _verify_payment,
}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mock": True}
