from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ToolDefinition(BaseModel):
    """Metadata for a single tool, as discovered from the Java Tool Layer's
    GET /tools. Used only for LLM reasoning / tool selection - the Python
    service never executes commerce operations itself; the Java Tool Layer
    (AgentToolRegistry -> AgentTool -> MerchantCommerceAdapter) remains the
    single place that does.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict, alias="inputSchema")
    output_schema: Optional[dict[str, Any]] = Field(default=None, alias="outputSchema")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCallResult(BaseModel):
    """A single tool's result, as returned by the Java Tool Layer's
    POST /tools/{toolName}/execute. Mirrors com.ecommerce.tools.model.ToolResponse
    (success / data / errorCode / errorMessage) exactly - see ToolClient.
    """

    model_config = ConfigDict(populate_by_name=True)

    success: bool
    data: Any = None
    error_code: Optional[str] = Field(default=None, alias="errorCode")
    error_message: Optional[str] = Field(default=None, alias="errorMessage")


# Tool names the agent may encounter. Only search_products, get_product,
# check_inventory, get_price, add_to_cart, update_cart, remove_from_cart,
# create_order, get_orders, and verify_payment currently exist in the Java
# Tool Layer - the rest are reserved names for tools that may be added
# there later. This list is for documentation/tests only; the agent's
# actual available tools always come from ToolClient.get_available_tools(),
# never from this constant.
KNOWN_TOOL_NAMES: tuple[str, ...] = (
    "search_products",
    "get_product",
    "check_inventory",
    "get_price",
    "add_to_cart",
    "update_cart",
    "remove_from_cart",
    "create_order",
    "get_orders",
    "verify_payment",
    # Reserved - not yet implemented in the Java Tool Layer:
    "track_order",
    "cancel_order",
)
