package com.ecommerce.tools.contract;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.util.Collections;
import java.util.Map;

/**
 * Standardized error payload carried on ToolResponse.error when success is
 * false.
 *
 * Pure data: this class never decides what to do about an error, logs
 * anything, or maps from an internal exception itself - it only describes
 * one. That translation (e.g. from ResourceNotFoundException, or from
 * com.ecommerce.tools.model.ToolResponse's errorCode/errorMessage) is the
 * HTTP boundary's job (AgentToolController), not this contract's.
 *
 * code    - specific, tool/domain-level identifier (e.g. "PRODUCT_NOT_FOUND").
 *           Free-form by design - the contract does not enumerate every
 *           possible code, since new tools introduce new specific failures.
 * type    - coarse category from the nested ToolErrorType - what a caller
 *           branches on generically, independent of which tool/code
 *           produced it.
 * message - human/LLM-readable explanation.
 * details - optional, arbitrary structured context. Never required.
 */
public class ToolError {

    /**
     * Small, fixed set of error categories every caller can branch on
     * generically, independent of the tool-specific ToolError.code. Kept
     * deliberately small - add a value only when an entire class of
     * callers needs to treat it differently, not for every new failure
     * mode a specific tool might have.
     */
    public enum ToolErrorType {
        VALIDATION_ERROR,
        NOT_FOUND,
        UNAUTHORIZED,
        FORBIDDEN,
        INVENTORY_UNAVAILABLE,
        PAYMENT_REQUIRED,
        TOOL_EXECUTION_ERROR,
        TIMEOUT,
        INTERNAL_ERROR
    }

    @NotBlank(message = "code is required")
    private String code;

    @NotBlank(message = "message is required")
    private String message;

    @NotNull(message = "type is required")
    private ToolErrorType type;

    private Map<String, Object> details = Collections.emptyMap();

    public ToolError() {
    }

    public ToolError(String code, String message, ToolErrorType type, Map<String, Object> details) {
        this.code = code;
        this.message = message;
        this.type = type;
        this.details = details == null ? Collections.emptyMap() : details;
    }

    public static ToolError of(String code, String message, ToolErrorType type) {
        return new ToolError(code, message, type, Collections.emptyMap());
    }

    public static ToolError of(String code, String message, ToolErrorType type, Map<String, Object> details) {
        return new ToolError(code, message, type, details);
    }

    public String getCode() {
        return code;
    }

    public void setCode(String code) {
        this.code = code;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public ToolErrorType getType() {
        return type;
    }

    public void setType(ToolErrorType type) {
        this.type = type;
    }

    public Map<String, Object> getDetails() {
        return details;
    }

    public void setDetails(Map<String, Object> details) {
        this.details = details == null ? Collections.emptyMap() : details;
    }
}
