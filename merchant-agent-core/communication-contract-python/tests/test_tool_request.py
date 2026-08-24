import json

import pytest
from pydantic import ValidationError

from contracts.tool_request import ToolRequest


def test_valid_request_parses_all_fields():
    request = ToolRequest(
        requestId="req-123",
        toolName="search_products",
        arguments={"query": "laptop", "maxPrice": 50000},
        context={"sessionId": "session-456", "currency": "INR"},
    )

    assert request.request_id == "req-123"
    assert request.tool_name == "search_products"
    assert request.arguments == {"query": "laptop", "maxPrice": 50000}
    assert request.context == {"sessionId": "session-456", "currency": "INR"}


def test_missing_request_id_is_rejected():
    with pytest.raises(ValidationError):
        ToolRequest(toolName="search_products")


def test_missing_tool_name_is_rejected():
    with pytest.raises(ValidationError):
        ToolRequest(requestId="req-123")


def test_empty_tool_name_is_rejected():
    with pytest.raises(ValidationError):
        ToolRequest(requestId="req-123", toolName="")


def test_empty_request_id_is_rejected():
    with pytest.raises(ValidationError):
        ToolRequest(requestId="", toolName="search_products")


def test_arguments_default_to_empty_dict_when_omitted():
    request = ToolRequest(requestId="req-123", toolName="search_products")

    assert request.arguments == {}


def test_context_is_optional_and_defaults_to_empty_dict():
    request = ToolRequest(requestId="req-123", toolName="search_products", arguments={"query": "laptop"})

    assert request.context == {}


def test_arguments_are_opaque_and_accept_arbitrary_shapes():
    # The contract must not assume anything about a tool's argument shape.
    request = ToolRequest(
        requestId="req-123",
        toolName="add_to_cart",
        arguments={"productId": 5, "quantity": 2, "nested": {"giftWrap": True}},
    )

    assert request.arguments["nested"] == {"giftWrap": True}


def test_json_serialization_uses_camel_case_wire_field_names():
    request = ToolRequest(
        requestId="req-123",
        toolName="search_products",
        arguments={"query": "laptop", "maxPrice": 50000},
        context={"sessionId": "session-456", "currency": "INR"},
    )

    payload = json.loads(request.model_dump_json(by_alias=True))

    assert payload == {
        "requestId": "req-123",
        "toolName": "search_products",
        "arguments": {"query": "laptop", "maxPrice": 50000},
        "context": {"sessionId": "session-456", "currency": "INR"},
    }


def test_json_deserialization_from_wire_format():
    raw = json.dumps(
        {
            "requestId": "req-123",
            "toolName": "search_products",
            "arguments": {"query": "laptop"},
            "context": {"sessionId": "session-456"},
        }
    )

    request = ToolRequest.model_validate_json(raw)

    assert request.request_id == "req-123"
    assert request.tool_name == "search_products"
    assert request.arguments == {"query": "laptop"}
    assert request.context == {"sessionId": "session-456"}


def test_json_deserialization_rejects_missing_required_fields():
    raw = json.dumps({"arguments": {"query": "laptop"}})

    with pytest.raises(ValidationError):
        ToolRequest.model_validate_json(raw)
