package com.ecommerce.tools.contract;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ToolResponseTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void successfulResponseCarriesResultAndNoError() {
        ToolResponse response = ToolResponse.success("req-123", Map.of("products", java.util.List.of()));

        assertTrue(response.getSuccess());
        assertEquals(Map.of("products", java.util.List.of()), response.getResult());
        assertNull(response.getError());
    }

    @Test
    void failedResponseCarriesErrorAndNoResult() {
        ToolError error = ToolError.of("INVENTORY_UNAVAILABLE", "Product is currently unavailable",
                ToolError.ToolErrorType.INVENTORY_UNAVAILABLE);

        ToolResponse response = ToolResponse.failure("req-123", error);

        assertFalse(response.getSuccess());
        assertNull(response.getResult());
        assertEquals("INVENTORY_UNAVAILABLE", response.getError().getCode());
    }

    @Test
    void requestIdPropagatesUnchanged() {
        ToolResponse response = ToolResponse.success("req-abc-999", null);

        assertEquals("req-abc-999", response.getRequestId());
    }

    @Test
    void resultSupportsArbitraryStructuredShapesNotJustProducts() {
        ToolResponse response = ToolResponse.success("req-123", Map.of("orderId", 42, "status", "PAID"));

        assertEquals(Map.of("orderId", 42, "status", "PAID"), response.getResult());
    }

    @Test
    void errorIsPresentOnlyWhenSuccessIsFalse() {
        ToolError error = ToolError.of("NOT_FOUND", "missing", ToolError.ToolErrorType.NOT_FOUND);

        ToolResponse failed = ToolResponse.failure("req-123", error);
        ToolResponse succeeded = ToolResponse.success("req-123", Map.of("ok", true));

        assertFalse(failed.getSuccess());
        assertTrue(succeeded.getSuccess());
        assertNull(succeeded.getError());
    }

    @Test
    void jsonSerializationOfSuccessfulResponseIncludesExplicitNullError() throws Exception {
        ToolResponse response = ToolResponse.success("req-123", Map.of("products", java.util.List.of()));

        String json = objectMapper.writeValueAsString(response);
        Map<?, ?> parsed = objectMapper.readValue(json, Map.class);

        assertEquals("req-123", parsed.get("requestId"));
        assertEquals(true, parsed.get("success"));
        assertEquals(Map.of("products", java.util.List.of()), parsed.get("result"));
        assertTrue(parsed.containsKey("error"));
        assertNull(parsed.get("error"));
    }

    @Test
    void jsonSerializationOfErrorResponseIncludesExplicitNullResult() throws Exception {
        ToolError error = ToolError.of("INVENTORY_UNAVAILABLE", "Product is currently unavailable",
                ToolError.ToolErrorType.INVENTORY_UNAVAILABLE);
        ToolResponse response = ToolResponse.failure("req-123", error);

        String json = objectMapper.writeValueAsString(response);
        Map<?, ?> parsed = objectMapper.readValue(json, Map.class);

        assertEquals(false, parsed.get("success"));
        assertTrue(parsed.containsKey("result"));
        assertNull(parsed.get("result"));
        assertEquals("INVENTORY_UNAVAILABLE", ((Map<?, ?>) parsed.get("error")).get("code"));
    }

    @Test
    void jsonDeserializationOfSuccessfulResponse() throws Exception {
        String json = """
                {
                  "requestId": "req-123",
                  "success": true,
                  "result": { "products": [] },
                  "error": null
                }
                """;

        ToolResponse response = objectMapper.readValue(json, ToolResponse.class);

        assertTrue(response.getSuccess());
        assertNull(response.getError());
    }

    @Test
    void jsonDeserializationOfErrorResponse() throws Exception {
        String json = """
                {
                  "requestId": "req-123",
                  "success": false,
                  "result": null,
                  "error": {
                    "code": "PRODUCT_NOT_FOUND",
                    "message": "Product was not found",
                    "type": "NOT_FOUND",
                    "details": {}
                  }
                }
                """;

        ToolResponse response = objectMapper.readValue(json, ToolResponse.class);

        assertFalse(response.getSuccess());
        assertEquals("PRODUCT_NOT_FOUND", response.getError().getCode());
        assertEquals(ToolError.ToolErrorType.NOT_FOUND, response.getError().getType());
    }
}
