package com.ecommerce.tools.model;

/**
 * Thrown by ToolRequest's getRequired* / getOptional* helpers (and tools
 * themselves, for cross-field checks) when agent-supplied input doesn't
 * pass validation. Caught by AbstractAgentTool and translated into a
 * ToolResponse with errorCode = "VALIDATION_ERROR" - it never escapes
 * to the agent layer as a raw exception.
 */
public class ToolValidationException extends RuntimeException {

    public ToolValidationException(String message) {
        super(message);
    }
}
