package com.ecommerce.tools.contract;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/**
 * The wire-format response the Java Tool Layer sends back to the Merchant
 * Agent Core for a single tool call.
 *
 * Pure data: this class never executes a tool, calls a merchant API, or
 * decides what a failure means - see AgentToolRegistry/AgentTool for that.
 * It only describes what comes back over the wire.
 *
 * requestId - must match the originating ToolRequest.requestId.
 * success   - whether the tool execution completed successfully.
 * result    - arbitrary structured tool output. The contract makes no
 *             assumption about its shape (it does not assume every tool
 *             returns e.g. a "products" list) - present when success is
 *             true, null when it's false.
 * error     - a ToolError; present when success is false, null when it's
 *             true.
 */
public class ToolResponse {

    @NotBlank(message = "requestId is required")
    private String requestId;

    @NotNull(message = "success is required")
    private Boolean success;

    private Object result;

    private ToolError error;

    public ToolResponse() {
    }

    private ToolResponse(String requestId, Boolean success, Object result, ToolError error) {
        this.requestId = requestId;
        this.success = success;
        this.result = result;
        this.error = error;
    }

    public static ToolResponse success(String requestId, Object result) {
        return new ToolResponse(requestId, true, result, null);
    }

    public static ToolResponse failure(String requestId, ToolError error) {
        return new ToolResponse(requestId, false, null, error);
    }

    public String getRequestId() {
        return requestId;
    }

    public void setRequestId(String requestId) {
        this.requestId = requestId;
    }

    public Boolean getSuccess() {
        return success;
    }

    public void setSuccess(Boolean success) {
        this.success = success;
    }

    public Object getResult() {
        return result;
    }

    public void setResult(Object result) {
        this.result = result;
    }

    public ToolError getError() {
        return error;
    }

    public void setError(ToolError error) {
        this.error = error;
    }
}
