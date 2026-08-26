from __future__ import annotations

import logging
from typing import Any, Union

from app.tools.tool_client import ToolClient, ToolClientError
from transaction.exceptions import OrderCreationError

logger = logging.getLogger(__name__)


def _coerce_user_id(user_id: Union[int, str]) -> Union[int, str]:
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return user_id


class OrderToolAdapter:
    """Thin wrapper around the existing get_orders tool.

    Order *creation* is not duplicated here: in this system it is an
    atomic side effect of RazorpayPaymentToolAdapter.create_checkout(), and
    order *confirmation* (marking PAID) is an atomic side effect of
    RazorpayPaymentToolAdapter.verify_payment() - both already reuse the
    existing OrderService, per MerchantCommerceAdapter's contract. This
    adapter exists only for the read path: looking up an order's current
    state (e.g. for PaymentService.get_payment_status(), or for a caller
    that wants an independent confirmation snapshot). If a standalone
    "confirm order" tool is ever added to the Java Tool Layer, wire it in
    here rather than in the orchestrator.
    """

    def __init__(self, tool_client: ToolClient):
        self._tool_client = tool_client

    def get_order(self, user_id: Union[int, str], order_id: str, request_id: str | None = None) -> dict[str, Any]:
        try:
            response = self._tool_client.execute_tool(
                "get_orders",
                arguments={"orderId": int(order_id)},
                user_id=_coerce_user_id(user_id),
                request_id=request_id,
            )
        except ToolClientError as exc:
            logger.error("get_orders tool call failed for order_id=%s: %s", order_id, exc)
            raise OrderCreationError(f"Could not reach the order service: {exc}") from exc

        if not response.success:
            raise OrderCreationError(response.error_message or f"Unable to retrieve order {order_id}")

        return response.data
