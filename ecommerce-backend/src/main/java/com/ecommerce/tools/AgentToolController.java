package com.ecommerce.tools;

import com.ecommerce.tools.contract.ToolError;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Minimal HTTP surface over AgentToolRegistry for the Python
 * merchant-agent-core service. Exposes tool discovery and execution via the
 * Communication Contract (ToolRequest / ToolResponse).
 */
@RestController
@RequestMapping("/tools")
public class AgentToolController {

    private final AgentToolRegistry agentToolRegistry;
    private final ObjectMapper objectMapper;

    public AgentToolController(AgentToolRegistry agentToolRegistry, ObjectMapper objectMapper) {
        this.agentToolRegistry = agentToolRegistry;
        this.objectMapper = objectMapper != null ? objectMapper : new ObjectMapper();
    }

    @GetMapping
    public ResponseEntity<Map<String, Object>> listTools() {
        List<Map<String, Object>> tools = agentToolRegistry.getAllTools().stream()
                .map(this::describe)
                .toList();

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("tools", tools);
        return ResponseEntity.ok(body);
    }

    @PostMapping("/execute")
    public ResponseEntity<com.ecommerce.tools.contract.ToolResponse> executeToolDirect(
            @RequestBody com.ecommerce.tools.contract.ToolRequest contractRequest) {
        return handleExecution(null, contractRequest);
    }

    @PostMapping("/{toolName}/execute")
    public ResponseEntity<com.ecommerce.tools.contract.ToolResponse> executeTool(
            @PathVariable String toolName,
            @RequestBody com.ecommerce.tools.contract.ToolRequest contractRequest) {
        return handleExecution(toolName, contractRequest);
    }

    private ResponseEntity<com.ecommerce.tools.contract.ToolResponse> handleExecution(
            String pathToolName,
            com.ecommerce.tools.contract.ToolRequest contractRequest) {

        String toolName = (contractRequest.getToolName() != null && !contractRequest.getToolName().isBlank())
                ? contractRequest.getToolName()
                : pathToolName;

        String requestId = contractRequest.getRequestId();
        if (requestId == null || requestId.isBlank()) {
            requestId = "req-" + UUID.randomUUID().toString().substring(0, 8);
        }

        Long userId = extractUserId(contractRequest.getContext());

        com.ecommerce.tools.model.ToolRequest internalRequest =
                new com.ecommerce.tools.model.ToolRequest(userId, contractRequest.getArguments());

        com.ecommerce.tools.model.ToolResponse internalResponse =
                agentToolRegistry.execute(toolName, internalRequest);

        if (internalResponse.isSuccess()) {
            return ResponseEntity.ok(
                    com.ecommerce.tools.contract.ToolResponse.success(requestId, internalResponse.getData())
            );
        } else {
            ToolError.ToolErrorType errorType = mapToErrorType(internalResponse.getErrorCode());
            ToolError contractError = ToolError.of(
                    internalResponse.getErrorCode() != null ? internalResponse.getErrorCode() : "UNKNOWN_ERROR",
                    internalResponse.getErrorMessage() != null ? internalResponse.getErrorMessage() : "Execution failed",
                    errorType
            );
            return ResponseEntity.ok(
                    com.ecommerce.tools.contract.ToolResponse.failure(requestId, contractError)
            );
        }
    }

    private Long extractUserId(Map<String, Object> context) {
        if (context == null || !context.containsKey("userId")) {
            return null;
        }
        Object val = context.get("userId");
        if (val instanceof Number) {
            return ((Number) val).longValue();
        }
        if (val instanceof String) {
            try {
                return Long.parseLong((String) val);
            } catch (NumberFormatException e) {
                return null;
            }
        }
        return null;
    }

    private ToolError.ToolErrorType mapToErrorType(String errorCode) {
        if (errorCode == null) {
            return ToolError.ToolErrorType.INTERNAL_ERROR;
        }
        return switch (errorCode) {
            case "VALIDATION_ERROR", "TOOL_NOT_FOUND" -> ToolError.ToolErrorType.VALIDATION_ERROR;
            case "NOT_FOUND" -> ToolError.ToolErrorType.NOT_FOUND;
            case "INSUFFICIENT_STOCK", "INVENTORY_UNAVAILABLE" -> ToolError.ToolErrorType.INVENTORY_UNAVAILABLE;
            case "PAYMENT_ERROR", "PAYMENT_REQUIRED" -> ToolError.ToolErrorType.PAYMENT_REQUIRED;
            case "UNAUTHORIZED" -> ToolError.ToolErrorType.UNAUTHORIZED;
            case "FORBIDDEN" -> ToolError.ToolErrorType.FORBIDDEN;
            case "TIMEOUT" -> ToolError.ToolErrorType.TIMEOUT;
            default -> ToolError.ToolErrorType.INTERNAL_ERROR;
        };
    }

    private Map<String, Object> describe(AgentTool tool) {
        Map<String, Object> description = new LinkedHashMap<>();
        description.put("name", tool.getName());
        description.put("description", tool.getDescription());
        description.put("inputSchema", parseSchema(tool.getInputSchema()));
        description.put("outputSchema", parseSchema(tool.getOutputSchema()));
        return description;
    }

    private JsonNode parseSchema(String schema) {
        try {
            return objectMapper.readTree(schema);
        } catch (Exception e) {
            return objectMapper.getNodeFactory().objectNode();
        }
    }
}
