from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentRequest(BaseModel):
    """The request object that crosses the Gateway -> Agent Orchestrator
    boundary.

    This is a pure data contract: the Gateway builds it after validation and
    authentication, and the Agent Orchestrator is the only thing that reads
    it. It carries no framework (FastAPI/HTTP) types so the Agent Core stays
    fully decoupled from the transport layer.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    request_id: str = Field(alias="requestId")
    session_id: str = Field(alias="sessionId")
    user_id: str = Field(alias="userId")
    message: str
    channel: str = "web"

    @staticmethod
    def new(
        session_id: str,
        user_id: str,
        message: str,
        channel: str = "web",
        request_id: Optional[str] = None,
    ) -> "AgentRequest":
        """Construct an AgentRequest, generating a requestId when the caller
        (the Gateway) does not already have one to propagate."""
        return AgentRequest(
            requestId=request_id or f"req-{uuid.uuid4()}",
            sessionId=session_id,
            userId=user_id,
            message=message,
            channel=channel,
        )
