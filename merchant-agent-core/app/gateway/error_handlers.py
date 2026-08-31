from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _request_id_from(request: Request) -> str:
    return getattr(request.state, "request_id", None) or f"req-{uuid.uuid4()}"


def _structured_error(request_id: str, http_status: int, message: str, code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={
            "requestId": request_id,
            "status": "FAILED",
            "message": message,
            "data": None,
            "error": {"code": code, "message": detail},
        },
    )


def register_gateway_error_handlers(app: FastAPI) -> None:
    """Registers the Gateway's structured, boundary-level error handling.

    - Malformed request bodies (missing sessionId/userId, wrong types, etc.)
      -> HTTP 400 with a structured error, instead of FastAPI's default 422.
    - Any other unhandled exception -> HTTP 500 with a structured error.
      The real exception (with stack trace) is only ever written to server
      logs, never returned to the client.
    """

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = _request_id_from(request)
        logger.error("Request validation failed for requestId=%s: %s", request_id, exc.errors())
        first_error = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(part) for part in first_error.get("loc", []) if part != "body")
        detail = first_error.get("msg", "Invalid request body")
        return _structured_error(
            request_id,
            status.HTTP_400_BAD_REQUEST,
            "Invalid request",
            "INVALID_REQUEST",
            f"{field}: {detail}" if field else detail,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id_from(request)
        logger.exception("Unhandled exception for requestId=%s", request_id)
        return _structured_error(
            request_id,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Unable to process the request",
            "INTERNAL_ERROR",
            "An unexpected error occurred",
        )
