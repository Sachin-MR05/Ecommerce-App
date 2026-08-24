package com.ecommerce.tools.contract;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import jakarta.validation.ValidatorFactory;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ToolRequestTest {

    private static ValidatorFactory validatorFactory;
    private static Validator validator;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @BeforeAll
    static void setUpValidator() {
        validatorFactory = Validation.buildDefaultValidatorFactory();
        validator = validatorFactory.getValidator();
    }

    @AfterAll
    static void tearDownValidator() {
        validatorFactory.close();
    }

    @Test
    void validRequestHasNoViolations() {
        ToolRequest request = new ToolRequest(
                "req-123", "search_products",
                Map.of("query", "laptop", "maxPrice", 50000),
                Map.of("sessionId", "session-456", "currency", "INR"));

        Set<ConstraintViolation<ToolRequest>> violations = validator.validate(request);

        assertTrue(violations.isEmpty());
    }

    @Test
    void missingRequestIdIsRejected() {
        ToolRequest request = new ToolRequest(null, "search_products", Map.of(), Map.of());

        Set<ConstraintViolation<ToolRequest>> violations = validator.validate(request);

        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("requestId")));
    }

    @Test
    void missingToolNameIsRejected() {
        ToolRequest request = new ToolRequest("req-123", null, Map.of(), Map.of());

        Set<ConstraintViolation<ToolRequest>> violations = validator.validate(request);

        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("toolName")));
    }

    @Test
    void emptyToolNameIsRejected() {
        ToolRequest request = new ToolRequest("req-123", "", Map.of(), Map.of());

        Set<ConstraintViolation<ToolRequest>> violations = validator.validate(request);

        assertFalse(violations.isEmpty());
    }

    @Test
    void argumentsDefaultToEmptyMapWhenNull() {
        ToolRequest request = new ToolRequest("req-123", "search_products", null, null);

        assertEquals(Map.of(), request.getArguments());
        assertEquals(Map.of(), request.getContext());
    }

    @Test
    void argumentsAcceptArbitraryNestedShapes() {
        ToolRequest request = new ToolRequest(
                "req-123", "add_to_cart",
                Map.of("productId", 5, "quantity", 2, "nested", Map.of("giftWrap", true)),
                Map.of());

        assertEquals(Map.of("giftWrap", true), request.getArguments().get("nested"));
    }

    @Test
    void jsonSerializationUsesExpectedWireFieldNames() throws Exception {
        ToolRequest request = new ToolRequest(
                "req-123", "search_products",
                Map.of("query", "laptop"),
                Map.of("sessionId", "session-456"));

        String json = objectMapper.writeValueAsString(request);
        Map<?, ?> parsed = objectMapper.readValue(json, Map.class);

        assertEquals("req-123", parsed.get("requestId"));
        assertEquals("search_products", parsed.get("toolName"));
        assertEquals(Map.of("query", "laptop"), parsed.get("arguments"));
        assertEquals(Map.of("sessionId", "session-456"), parsed.get("context"));
    }

    @Test
    void jsonDeserializationFromWireFormat() throws Exception {
        String json = """
                {
                  "requestId": "req-123",
                  "toolName": "search_products",
                  "arguments": { "query": "laptop" },
                  "context": { "sessionId": "session-456" }
                }
                """;

        ToolRequest request = objectMapper.readValue(json, ToolRequest.class);

        assertEquals("req-123", request.getRequestId());
        assertEquals("search_products", request.getToolName());
        assertEquals("laptop", request.getArguments().get("query"));
        assertEquals("session-456", request.getContext().get("sessionId"));
    }
}
