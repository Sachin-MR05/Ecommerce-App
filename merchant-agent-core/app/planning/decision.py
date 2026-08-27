from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class DecisionAction(str, Enum):
    TOOL_CALL = "TOOL_CALL"
    FINAL_RESPONSE = "FINAL_RESPONSE"
    ASK_USER = "ASK_USER"
    SELECT_PRODUCT = "SELECT_PRODUCT"


class Decision(BaseModel):
    """The structured decision the planner extracts from the LLM's output
    for a single iteration of the agent loop.

    Only what's needed to execute or conclude the loop is kept here - an
    optional short rationale for debugging/observability, never the model's
    full hidden reasoning.
    """

    action: DecisionAction

    tool_name: Optional[str] = None
    arguments: dict[str, Any] = Field(default_factory=dict)

    response: Optional[str] = None
    clarification_question: Optional[str] = None
    
    selected_product_id: Optional[int] = None
    selected_quantity: Optional[int] = None

    rationale: Optional[str] = None

    @model_validator(mode="after")
    def _validate_shape_matches_action(self) -> "Decision":
        if self.action == DecisionAction.TOOL_CALL and not self.tool_name:
            raise ValueError("A TOOL_CALL decision must include tool_name")
        if self.action == DecisionAction.FINAL_RESPONSE and not self.response:
            raise ValueError("A FINAL_RESPONSE decision must include response")
        if self.action == DecisionAction.ASK_USER and not self.clarification_question:
            raise ValueError("An ASK_USER decision must include clarification_question")
        if self.action == DecisionAction.SELECT_PRODUCT and (self.selected_product_id is None or self.selected_quantity is None):
            raise ValueError("A SELECT_PRODUCT decision must include selected_product_id and selected_quantity")
        return self
