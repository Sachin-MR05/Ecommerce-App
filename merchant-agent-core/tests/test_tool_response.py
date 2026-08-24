import json

import pytest
from pydantic import ValidationError

from contracts.tool_error import ToolError, ToolErrorType
from contracts.tool_response import ToolResponse


def test_successful_response_carries_result_and_no_error():
    response = ToolResponse(requestId="req-123", success=True, result={"products": []})

    assert response.success is True
    assert response.result == {"products": []}
    assert response.error is None


def test_failed_response_carries_error_and_no_result():
    error = ToolError(code="INVENTORY_UNAVAILABLE", message="Product is currently unavailable",
                       type=ToolErrorType.INVENTORY_UNAVAILABLE)

    response = ToolResponse(requestId="req-123", success=False, error=error)

    assert response.success is False
    assert response.result is None
    assert response.error.code == "INVENTORY_UNAVAILABLE"


def test_request_id_propagates_unchanged():
    response = ToolResponse(requestId="req-abc-999", success=True, result=None)

    assert response.request_id == "req-abc-999"


def test_result_supports_arbitrary_structured_shapes_not_just_products():
    response = ToolResponse(requestId="req-123", success=True, result={"orderId": 42, "status": "PAID"})

    assert response.result == {"orderId": 42, "status": "PAID"}


def test_successful_response_with_error_is_rejected():
    error = ToolError(code="NOT_FOUND", message="missing", type=ToolErrorType.NOT_FOUND)

    with pytest.raises(ValidationError):
        ToolResponse(requestId="req-123", success=True, result={"ok": True}, error=error)


def test_failed_response_without_error_is_rejected():
    with pytest.raises(ValidationError):
        ToolResponse(requestId="req-123", success=False)


def test_missing_request_id_is_rejected():
    with pytest.raises(ValidationError):
        ToolResponse(success=True, result={})


def test_json_serialization_matches_wire_format_with_explicit_nulls():
    response = ToolResponse(requestId="req-123", success=True, result={"products": []})

    payload = json.loads(response.model_dump_json(by_alias=True))

    assert payload == {"requestId": "req-123", "success": True, "result": {"products": []}, "error": None}


def test_json_serialization_of_error_response():
    error = ToolError(
        code="INVENTORY_UNAVAILABLE",
        message="Product is currently unavailable",
        type=ToolErrorType.INVENTORY_UNAVAILABLE,
    )
    response = ToolResponse(requestId="req-123", success=False, error=error)

    payload = json.loads(response.model_dump_json(by_alias=True))

    assert payload == {
        "requestId": "req-123",
        "success": False,
        "result": None,
        "error": {
            "code": "INVENTORY_UNAVAILABLE",
            "message": "Product is currently unavailable",
            "type": "INVENTORY_UNAVAILABLE",
            "details": {},
        },
    }


def test_json_deserialization_of_successful_response():
    raw = json.dumps({"requestId": "req-123", "success": True, "result": {"products": []}, "error": None})

    response = ToolResponse.model_validate_json(raw)

    assert response.success is True
    assert response.result == {"products": []}


def test_json_deserialization_of_error_response():
    raw = json.dumps(
        {
            "requestId": "req-123",
            "success": False,
            "result": None,
            "error": {
                "code": "PRODUCT_NOT_FOUND",
                "message": "Product was not found",
                "type": "NOT_FOUND",
                "details": {},
            },
        }
    )

    response = ToolResponse.model_validate_json(raw)

    assert response.success is False
    assert response.error.code == "PRODUCT_NOT_FOUND"
    assert response.error.type == ToolErrorType.NOT_FOUND
