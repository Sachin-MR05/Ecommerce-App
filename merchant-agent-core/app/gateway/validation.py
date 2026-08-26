from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

MAX_MESSAGE_LENGTH = 4000
ALLOWED_CHANNELS = {"web", "mobile", "api", "voice", "chat"}


@dataclass
class ValidationError:
    code: str
    message: str


def validate_incoming_message(
    session_id: Optional[str],
    user_id: Optional[str],
    message: Optional[str],
    channel: Optional[str],
) -> Optional[ValidationError]:
    """Pure, deterministic HTTP/API-input validation.

    This is intentionally dumb: no LLM calls, no business rules (e.g. no
    inventory checks, no "is this product real" checks). It only validates
    the shape of the request before it is allowed to become an AgentRequest.
    Returns None when the request is valid.
    """

    if not session_id or not session_id.strip():
        return ValidationError(code="MISSING_SESSION_ID", message="sessionId is required")

    if not user_id or not user_id.strip():
        return ValidationError(code="MISSING_USER_ID", message="userId is required")

    if message is None or not message.strip():
        return ValidationError(code="EMPTY_MESSAGE", message="message cannot be empty")

    if len(message) > MAX_MESSAGE_LENGTH:
        return ValidationError(
            code="MESSAGE_TOO_LONG",
            message=f"message must be {MAX_MESSAGE_LENGTH} characters or fewer",
        )

    if channel and channel not in ALLOWED_CHANNELS:
        return ValidationError(
            code="INVALID_CHANNEL",
            message=f"channel must be one of: {', '.join(sorted(ALLOWED_CHANNELS))}",
        )

    return None
