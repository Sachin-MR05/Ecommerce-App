from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.tool_error import ToolError


class ToolResponse(BaseModel):
    """The wire-format response the Java Tool Layer sends back to the
    Merchant Agent Core for a single tool call.

    Pure data: this class never executes anything, calls a tool, or talks
    to the Java Tool Layer - see app/tools/tool_client.py for that. It
    only describes the shape of what comes back.

    requestId - must match the originating ToolRequest.requestId.
    success   - whether the tool execution completed successfully.
    result    - arbitrary structured tool output. The contract makes no
                assumption about its shape (it does not assume every tool
                returns e.g. a "products" list) - present when success is
                true, absent (null) when it's false.
    error     - a ToolError; present when success is false, absent (null)
                when it's true.
    """

    model_config = ConfigDict(populate_by_name=True)

    request_id: str = Field(..., min_length=1, alias="requestId")
    success: bool
    result: Optional[Any] = None
    error: Optional[ToolError] = None

    @model_validator(mode="after")
    def _error_presence_matches_success(self) -> "ToolResponse":
        if self.success and self.error is not None:
            raise ValueError("A successful ToolResponse (success=true) must not carry an error")
        if not self.success and self.error is None:
            raise ValueError("A failed ToolResponse (success=false) must carry an error")
        return self
