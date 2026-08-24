package com.ecommerce.tools.model;

/**
 * Uniform, structured result every AgentTool returns - success or failure -
 * so the agent layer never has to deal with a raw exception or an
 * inconsistent shape regardless of which tool it called.
 *
 * errorCode is a small, stable vocabulary an LLM/orchestrator can branch on:
 *   VALIDATION_ERROR    - the tool's input didn't pass validation
 *   NOT_FOUND            - referenced product/cart item/order doesn't exist
 *   INSUFFICIENT_STOCK   - requested quantity exceeds available stock
 *   PAYMENT_ERROR        - checkout/payment could not be completed
 *   INTERNAL_ERROR       - unexpected failure; message is intentionally generic
 */
public class ToolResponse {

    private final boolean success;
    private final Object data;
    private final String errorCode;
    private final String errorMessage;

    private ToolResponse(boolean success, Object data, String errorCode, String errorMessage) {
        this.success = success;
        this.data = data;
        this.errorCode = errorCode;
        this.errorMessage = errorMessage;
    }

    public static ToolResponse success(Object data) {
        return new ToolResponse(true, data, null, null);
    }

    public static ToolResponse failure(String errorCode, String errorMessage) {
        return new ToolResponse(false, null, errorCode, errorMessage);
    }

    public boolean isSuccess() {
        return success;
    }

    public Object getData() {
        return data;
    }

    public String getErrorCode() {
        return errorCode;
    }

    public String getErrorMessage() {
        return errorMessage;
    }
}
