from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from app.llm.llm_client import LLMMessage
from app.tools.tool_schema import ToolCallResult, ToolDefinition


class AgentStatus(str, Enum):
    INITIALIZED = "INITIALIZED"
    THINKING = "THINKING"
    TOOL_CALL = "TOOL_CALL"
    OBSERVING = "OBSERVING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    WAITING_FOR_USER = "WAITING_FOR_USER"


@dataclass
class ToolCallRecord:
    """One tool call and its outcome, kept on the state for
    observation/debugging and for the LLM's next reasoning step."""

    tool_name: str
    arguments: dict[str, Any]
    result: Optional[ToolCallResult] = None
    error: Optional[str] = None


@dataclass
class AgentState:
    """Explicit, self-contained state for a single agent execution.

    Each user request creates its own AgentState (see AgentState.create) -
    nothing here is process-global or shared/mutated across requests, so
    concurrent requests never interfere with each other.
    """

    session_id: str
    user_request: str
    user_id: Optional[int] = None
    request_id: Optional[str] = None

    messages: list[LLMMessage] = field(default_factory=list)
    available_tools: list[ToolDefinition] = field(default_factory=list)

    selected_tool: Optional[str] = None
    tool_arguments: dict[str, Any] = field(default_factory=dict)
    tool_results: list[ToolCallRecord] = field(default_factory=list)

    iteration: int = 0
    status: AgentStatus = AgentStatus.INITIALIZED
    final_response: Optional[str] = None
    error: Optional[str] = None
    
    selected_product_id: Optional[int] = None
    selected_quantity: Optional[int] = None

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def create(
        user_request: str,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None,
        request_id: Optional[str] = None,
    ) -> "AgentState":
        return AgentState(
            session_id=session_id or str(uuid.uuid4()),
            user_request=user_request,
            user_id=user_id,
            request_id=request_id,
        )

    def add_message(self, role: str, content: str) -> None:
        self.messages.append(LLMMessage(role=role, content=content))

    def record_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> None:
        self.selected_tool = tool_name
        self.tool_arguments = arguments
        self.tool_results.append(ToolCallRecord(tool_name=tool_name, arguments=arguments))

    def record_tool_result(self, result: ToolCallResult) -> None:
        if self.tool_results:
            self.tool_results[-1].result = result

    def record_tool_error(self, error_message: str) -> None:
        if self.tool_results:
            self.tool_results[-1].error = error_message

    def increment_iteration(self) -> int:
        self.iteration += 1
        return self.iteration

    def complete(self, response: str) -> None:
        self.final_response = response
        self.status = AgentStatus.COMPLETED

    def fail(self, error_message: str) -> None:
        self.error = error_message
        self.status = AgentStatus.FAILED

    def wait_for_user(self, clarification: str) -> None:
        self.final_response = clarification
        self.status = AgentStatus.WAITING_FOR_USER
