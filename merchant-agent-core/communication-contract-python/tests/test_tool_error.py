import json

import pytest
from pydantic import ValidationError

from contracts.tool_error import ToolError, ToolErrorType


def test_valid_error_parses_all_fields():
    error = ToolError(
        code="PRODUCT_NOT_FOUND",
        message="Product was not found",
        type=ToolErrorType.NOT_FOUND,
        details={"productId": 999},
    )

    assert error.code == "PRODUCT_NOT_FOUND"
    assert error.message == "Product was not found"
    assert error.type == ToolErrorType.NOT_FOUND
    assert error.details == {"productId": 999}


def test_missing_code_is_rejected():
    with pytest.raises(ValidationError):
        ToolError(message="Product was not found", type=ToolErrorType.NOT_FOUND)


def test_missing_message_is_rejected():
    with pytest.raises(ValidationError):
        ToolError(code="PRODUCT_NOT_FOUND", type=ToolErrorType.NOT_FOUND)


def test_missing_type_is_rejected():
    with pytest.raises(ValidationError):
        ToolError(code="PRODUCT_NOT_FOUND", message="Product was not found")


def test_type_must_be_one_of_the_standardized_categories():
    with pytest.raises(ValidationError):
        ToolError(code="PRODUCT_NOT_FOUND", message="Product was not found", type="SOMETHING_MADE_UP")


def test_details_are_optional_and_default_to_empty_dict():
    error = ToolError(code="PRODUCT_NOT_FOUND", message="Product was not found", type=ToolErrorType.NOT_FOUND)

    assert error.details == {}


def test_json_serialization_matches_wire_format():
    error = ToolError(code="PRODUCT_NOT_FOUND", message="Product was not found", type=ToolErrorType.NOT_FOUND)

    payload = json.loads(error.model_dump_json())

    assert payload == {
        "code": "PRODUCT_NOT_FOUND",
        "message": "Product was not found",
        "type": "NOT_FOUND",
        "details": {},
    }


def test_json_deserialization_from_wire_format():
    raw = json.dumps(
        {
            "code": "INVENTORY_UNAVAILABLE",
            "message": "Product is currently unavailable",
            "type": "INVENTORY_UNAVAILABLE",
            "details": {"productId": 42},
        }
    )

    error = ToolError.model_validate_json(raw)

    assert error.code == "INVENTORY_UNAVAILABLE"
    assert error.type == ToolErrorType.INVENTORY_UNAVAILABLE
    assert error.details == {"productId": 42}
