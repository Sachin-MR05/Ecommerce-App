"""Reserved for a future CartToolAdapter.

The Java Tool Layer does not currently expose a standalone "get_cart" (or
"validate_cart") tool to the Python agent - only add_to_cart, update_cart,
and remove_from_cart (mutations). Cart validation, live pricing, and total
calculation are instead performed atomically inside the create_order tool
(see RazorpayPaymentToolAdapter.create_checkout and OrderService.checkout in
the Java Tool Layer), specifically to avoid a check-then-charge race
between validating the cart and creating the payment order.

If a read-only cart tool is added later, introduce a CartToolAdapter here
following the same pattern as tools/order/order_tool_adapter.py - a thin
ToolClient wrapper, no business logic - rather than having
TransactionOrchestrator re-derive cart/pricing logic itself.
"""
