import httpx
import pytest

from app.config.settings import Settings
from app.tools.tool_client import (
    MalformedToolResponseError,
    ToolClient,
    ToolServiceTimeoutError,
    ToolServiceUnavailableError,
)


def _settings() -> Settings:
    return Settings(TOOL_SERVICE_URL="http://tool-service.test")


def _client_with_transport(transport: httpx.MockTransport) -> ToolClient:
    settings = _settings()
    http_client = httpx.Client(base_url=settings.tool_service_url, transport=transport)
    return ToolClient(settings, client=http_client)


def test_get_available_tools_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/tools"
        return httpx.Response(
            200,
            json={"tools": [{"name": "search_products", "description": "search", "inputSchema": {}}]},
        )

    client = _client_with_transport(httpx.MockTransport(handler))

    tools = client.get_available_tools()

    assert len(tools) == 1
    assert tools[0].name == "search_products"


def test_execute_tool_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/tools/search_products/execute"
        assert request.method == "POST"
        return httpx.Response(
            200, json={"success": True, "data": [{"id": 1}], "errorCode": None, "errorMessage": None}
        )

    client = _client_with_transport(httpx.MockTransport(handler))

    result = client.execute_tool("search_products", {"keyword": "headphones"})

    assert result.success is True
    assert result.data == [{"id": 1}]


def test_execute_tool_reports_business_failure_without_raising():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"success": False, "data": None, "errorCode": "NOT_FOUND", "errorMessage": "missing"}
        )

    client = _client_with_transport(httpx.MockTransport(handler))

    result = client.execute_tool("get_product", {"productId": 999})

    assert result.success is False
    assert result.error_code == "NOT_FOUND"
    assert result.error_message == "missing"


def test_http_5xx_raises_unavailable_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = _client_with_transport(httpx.MockTransport(handler))

    with pytest.raises(ToolServiceUnavailableError):
        client.get_available_tools()


def test_timeout_raises_timeout_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = _client_with_transport(httpx.MockTransport(handler))

    with pytest.raises(ToolServiceTimeoutError):
        client.get_available_tools()


def test_connection_error_raises_unavailable_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = _client_with_transport(httpx.MockTransport(handler))

    with pytest.raises(ToolServiceUnavailableError):
        client.get_available_tools()


def test_malformed_tools_response_raises_malformed_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    client = _client_with_transport(httpx.MockTransport(handler))

    with pytest.raises(MalformedToolResponseError):
        client.get_available_tools()


def test_malformed_execute_response_raises_malformed_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    client = _client_with_transport(httpx.MockTransport(handler))

    with pytest.raises(MalformedToolResponseError):
        client.execute_tool("search_products", {})
