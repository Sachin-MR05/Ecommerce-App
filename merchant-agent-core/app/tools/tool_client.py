from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.config.settings import Settings
from app.tools.tool_schema import ToolCallResult, ToolDefinition

logger = logging.getLogger(__name__)


class ToolClientError(Exception):
    """Base error for anything that goes wrong talking to the Java Tool Layer.
    Tool failures are never silently swallowed: transport/HTTP problems raise
    a subclass of this; a *business* tool failure (HTTP 200, success=false)
    is returned as a ToolCallResult for the caller to observe, never hidden.
    """


class ToolServiceUnavailableError(ToolClientError):
    """The Java Tool Layer could not be reached, or returned a server error."""


class ToolServiceTimeoutError(ToolClientError):
    """The Java Tool Layer did not respond within TOOL_TIMEOUT_SECONDS."""


class MalformedToolResponseError(ToolClientError):
    """The Java Tool Layer responded, but the payload didn't match the
    expected /tools or /tools/{name}/execute shape."""


class ToolClient:
    """HTTP client for the Java Tool Layer (AgentToolRegistry, exposed over
    HTTP by AgentToolController - see the README for the exact contract).

    This is the ONLY place in the Python service that talks to Java. It
    contains no commerce/tool-selection logic - it only discovers tool
    metadata and forwards execution requests, translating HTTP/JSON
    concerns into typed Python models (or a raised ToolClientError).
    """

    def __init__(self, settings: Settings, client: Optional[httpx.Client] = None):
        self._base_url = settings.tool_service_url.rstrip("/")
        self._timeout = settings.tool_timeout_seconds
        self._client = client or httpx.Client(base_url=self._base_url, timeout=self._timeout)

    def close(self) -> None:
        self._client.close()

    def get_available_tools(self) -> list[ToolDefinition]:
        """GET /tools - discover the tools currently registered in
        AgentToolRegistry, for LLM reasoning/tool selection."""
        logger.info("Discovering available tools from Java Tool Layer at %s", self._base_url)
        response = self._send("GET", "/tools")

        try:
            payload = response.json()
            tools = [ToolDefinition.model_validate(item) for item in payload["tools"]]
        except (KeyError, TypeError, ValueError) as exc:
            logger.error("Malformed GET /tools response from Java Tool Layer: %s", exc)
            raise MalformedToolResponseError("Malformed response from GET /tools") from exc

        logger.info("Discovered %d tool(s): %s", len(tools), [t.name for t in tools])
        return tools

    def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        user_id: Optional[int] = None,
    ) -> ToolCallResult:
        """POST /tools/{toolName}/execute - run a single tool call.

        Returns a ToolCallResult regardless of whether the tool itself
        succeeded or failed (success=false is a legitimate business
        outcome the caller must inspect) - it only raises for transport
        failures or a response that couldn't be understood at all.
        """
        logger.info("Executing tool '%s'", tool_name)
        body: dict[str, Any] = {"arguments": arguments}
        if user_id is not None:
            body["userId"] = user_id

        response = self._send("POST", f"/tools/{tool_name}/execute", json_body=body)

        try:
            result = ToolCallResult.model_validate(response.json())
        except (TypeError, ValueError) as exc:
            logger.error("Malformed execute response for tool '%s': %s", tool_name, exc)
            raise MalformedToolResponseError(f"Malformed response executing tool '{tool_name}'") from exc

        if result.success:
            logger.info("Tool '%s' executed successfully", tool_name)
        else:
            logger.warning(
                "Tool '%s' reported failure: %s - %s", tool_name, result.error_code, result.error_message
            )

        return result

    def _send(self, method: str, path: str, json_body: Optional[dict[str, Any]] = None) -> httpx.Response:
        try:
            response = self._client.request(method, path, json=json_body)
        except httpx.TimeoutException as exc:
            logger.error("Timed out calling Java Tool Layer %s %s", method, path)
            raise ToolServiceTimeoutError(f"Timed out calling {method} {path}") from exc
        except httpx.RequestError as exc:
            logger.error("Could not reach Java Tool Layer at %s%s: %s", self._base_url, path, exc)
            raise ToolServiceUnavailableError(f"Could not reach tool service: {exc}") from exc

        self._raise_for_http_error(response)
        return response

    def _raise_for_http_error(self, response: httpx.Response) -> None:
        if response.status_code == 404:
            raise ToolClientError(f"Tool endpoint not found: {response.request.url}")
        if response.status_code >= 500:
            raise ToolServiceUnavailableError(
                f"Java Tool Layer returned {response.status_code} for {response.request.url}"
            )
        if response.status_code >= 400:
            raise ToolClientError(
                f"Java Tool Layer rejected the request ({response.status_code}): {response.text}"
            )
