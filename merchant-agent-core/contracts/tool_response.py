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

    Convenience accessors (not part of the wire format):
      .data          - alias for result; used by ToolClient and agent internals.
      .error_code    - error.code when success is False, else None.
      .error_message - error.message when success is False, else None.
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

    # ------------------------------------------------------------------
    # Convenience properties used by ToolClient and agent-layer code.
    # These are NOT serialised - they are computed from the wire fields.
    # ------------------------------------------------------------------

    @property
    def data(self) -> Optional[Any]:
        """Alias for `result` - the successful tool output payload."""
        return self.result

    @property
    def error_code(self) -> Optional[str]:
        """The domain-specific error code (e.g. 'NOT_FOUND') when success
        is False, None when success is True."""
        return self.error.code if self.error is not None else None

    @property
    def error_message(self) -> Optional[str]:
        """The human/LLM-readable error explanation when success is False,
        None when success is True."""
        return self.error.message if self.error is not None else None

