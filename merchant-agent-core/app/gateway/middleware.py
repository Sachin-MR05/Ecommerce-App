from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.gateway.access")

# Header names that must never be logged, even at DEBUG level.
_SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Structured, safe request logging for every HTTP call through the
    Gateway.

    Logs requestId/sessionId/userId (when the route stashed them on
    request.state - see gateway/routes.py), method, path, status code, and
    processing duration. Never logs headers, tokens, passwords, or full
    request bodies.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()

        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            state = request.state
            logger.info(
                "requestId=%s sessionId=%s userId=%s method=%s endpoint=%s status=%s duration=%.1fms",
                getattr(state, "request_id", "-"),
                getattr(state, "session_id", "-"),
                getattr(state, "user_id", "-"),
                request.method,
                request.url.path,
                response.status_code if response is not None else "-",
                duration_ms,
            )
