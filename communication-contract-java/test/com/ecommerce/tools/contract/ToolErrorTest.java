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
import static org.junit.jupiter.api.Assertions.assertThrows;

class ToolErrorTest {

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
    void validErrorHasNoViolations() {
        ToolError error = ToolError.of(
                "PRODUCT_NOT_FOUND", "Product was not found", ToolError.ToolErrorType.NOT_FOUND, Map.of("productId", 999));

        Set<ConstraintViolation<ToolError>> violations = validator.validate(error);

        assertTrue(violations.isEmpty());
        assertEquals(Map.of("productId", 999), error.getDetails());
    }

    @Test
    void missingCodeIsRejected() {
        ToolError error = new ToolError(null, "Product was not found", ToolError.ToolErrorType.NOT_FOUND, Map.of());

        Set<ConstraintViolation<ToolError>> violations = validator.validate(error);

        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("code")));
    }

    @Test
    void missingMessageIsRejected() {
        ToolError error = new ToolError("PRODUCT_NOT_FOUND", null, ToolError.ToolErrorType.NOT_FOUND, Map.of());

        Set<ConstraintViolation<ToolError>> violations = validator.validate(error);

        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("message")));
    }

    @Test
    void missingTypeIsRejected() {
        ToolError error = new ToolError("PRODUCT_NOT_FOUND", "Product was not found", null, Map.of());

        Set<ConstraintViolation<ToolError>> violations = validator.validate(error);

        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("type")));
    }

    @Test
    void detailsAreOptionalAndDefaultToEmptyMap() {
        ToolError error = ToolError.of("PRODUCT_NOT_FOUND", "Product was not found", ToolError.ToolErrorType.NOT_FOUND);

        assertEquals(Map.of(), error.getDetails());
    }

    @Test
    void jsonSerializationMatchesWireFormat() throws Exception {
        ToolError error = ToolError.of("PRODUCT_NOT_FOUND", "Product was not found", ToolError.ToolErrorType.NOT_FOUND);

        String json = objectMapper.writeValueAsString(error);
        Map<?, ?> parsed = objectMapper.readValue(json, Map.class);

        assertEquals("PRODUCT_NOT_FOUND", parsed.get("code"));
        assertEquals("Product was not found", parsed.get("message"));
        assertEquals("NOT_FOUND", parsed.get("type"));
        assertEquals(Map.of(), parsed.get("details"));
    }

    @Test
    void jsonDeserializationFromWireFormat() throws Exception {
        String json = """
                {
                  "code": "INVENTORY_UNAVAILABLE",
                  "message": "Product is currently unavailable",
                  "type": "INVENTORY_UNAVAILABLE",
                  "details": { "productId": 42 }
                }
                """;

        ToolError error = objectMapper.readValue(json, ToolError.class);

        assertEquals("INVENTORY_UNAVAILABLE", error.getCode());
        assertEquals(ToolError.ToolErrorType.INVENTORY_UNAVAILABLE, error.getType());
        assertEquals(42, error.getDetails().get("productId"));
    }

    @Test
    void jsonDeserializationRejectsUnknownErrorType() {
        String json = """
                {
                  "code": "SOMETHING",
                  "message": "unexpected",
                  "type": "SOMETHING_MADE_UP",
                  "details": {}
                }
                """;

        assertThrows(Exception.class, () -> objectMapper.readValue(json, ToolError.class));
    }
}
