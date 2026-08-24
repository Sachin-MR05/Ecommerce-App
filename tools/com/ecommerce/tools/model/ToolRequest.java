package com.ecommerce.tools.model;

import java.util.Collections;
import java.util.Map;

/**
 * Provider-agnostic input envelope for a single tool call.
 *
 * userId is the authenticated caller's id, supplied by the calling
 * session/orchestrator (e.g. resolved from a JWT the same way
 * CurrentUser/UserPrincipal already does for the HTTP layer) - it is
 * NEVER read from the agent/LLM-supplied parameters map, so a tool
 * argument can't be used to act on someone else's cart or orders.
 *
 * parameters holds whatever arguments the agent/LLM supplied, matching
 * the shape described by the tool's getInputSchema(). Values typically
 * arrive as String/Integer/Long/Double/Boolean, however the calling
 * framework (OpenAI function calling, Gemini function declarations,
 * Claude tool_use, etc.) deserializes its JSON - the getRequired*/
 * getOptional* helpers below tolerate that variance.
 */
public class ToolRequest {

    private final Long userId;
    private final Map<String, Object> parameters;

    public ToolRequest(Long userId, Map<String, Object> parameters) {
        this.userId = userId;
        this.parameters = parameters == null ? Collections.emptyMap() : parameters;
    }

    public Long getUserId() {
        return userId;
    }

    public Map<String, Object> getParameters() {
        return parameters;
    }

    public boolean has(String key) {
        return parameters.get(key) != null;
    }

    public String getRequiredString(String key) {
        Object value = parameters.get(key);
        if (!(value instanceof String) || ((String) value).isBlank()) {
            throw new ToolValidationException("Missing or invalid required parameter: '" + key + "' (expected a non-blank string)");
        }
        return (String) value;
    }

    public String getOptionalString(String key) {
        Object value = parameters.get(key);
        if (value == null) {
            return null;
        }
        if (!(value instanceof String)) {
            throw new ToolValidationException("Parameter '" + key + "' must be a string");
        }
        String stringValue = (String) value;
        return stringValue.isBlank() ? null : stringValue;
    }

    public Long getRequiredLong(String key) {
        Long parsed = toLong(parameters.get(key));
        if (parsed == null) {
            throw new ToolValidationException("Missing or invalid required parameter: '" + key + "' (expected a whole number)");
        }
        return parsed;
    }

    public Long getOptionalLong(String key) {
        if (!has(key)) {
            return null;
        }
        Long parsed = toLong(parameters.get(key));
        if (parsed == null) {
            throw new ToolValidationException("Parameter '" + key + "' must be a whole number");
        }
        return parsed;
    }

    public int getRequiredInt(String key) {
        return Math.toIntExact(getRequiredLong(key));
    }

    public Integer getOptionalInt(String key, Integer defaultValue) {
        Long parsed = getOptionalLong(key);
        return parsed == null ? defaultValue : Math.toIntExact(parsed);
    }

    private Long toLong(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number) {
            return ((Number) value).longValue();
        }
        if (value instanceof String) {
            try {
                return Long.parseLong(((String) value).trim());
            } catch (NumberFormatException e) {
                return null;
            }
        }
        return null;
    }
}
