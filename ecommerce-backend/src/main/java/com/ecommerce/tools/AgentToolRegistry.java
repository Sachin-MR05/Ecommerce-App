package com.ecommerce.tools;

import com.ecommerce.tools.model.ToolRequest;
import com.ecommerce.tools.model.ToolResponse;
import org.springframework.stereotype.Component;

import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Central registry the agent layer uses to discover and invoke tools,
 * independent of which LLM/agent framework is driving it.
 *
 * Every AgentTool implementation is a Spring @Component, so Spring injects
 * the full list here automatically - adding a new tool means adding a new
 * @Component class, never touching this registry.
 */
@Component
public class AgentToolRegistry {

    private final Map<String, AgentTool> toolsByName;

    public AgentToolRegistry(List<AgentTool> tools) {
        Map<String, AgentTool> registered = new LinkedHashMap<>();
        for (AgentTool tool : tools) {
            AgentTool previous = registered.put(tool.getName(), tool);
            if (previous != null) {
                throw new IllegalStateException(
                        "Duplicate AgentTool name '" + tool.getName() + "' registered by both " +
                                previous.getClass().getName() + " and " + tool.getClass().getName());
            }
        }
        this.toolsByName = registered;
    }

    /**
     * All tools currently registered, in a stable order - typically used to
     * build the function/tool definitions handed to an LLM provider.
     */
    public Collection<AgentTool> getAllTools() {
        return toolsByName.values();
    }

    public Optional<AgentTool> getTool(String name) {
        return Optional.ofNullable(toolsByName.get(name));
    }

    public boolean isRegistered(String name) {
        return toolsByName.containsKey(name);
    }

    /**
     * Looks up a tool by name and executes it, returning a structured
     * ToolResponse either way - an unknown tool name is reported the same
     * way a validation error would be, never as an exception.
     */
    public ToolResponse execute(String toolName, ToolRequest request) {
        AgentTool tool = toolsByName.get(toolName);
        if (tool == null) {
            return ToolResponse.failure("TOOL_NOT_FOUND", "No tool registered with name: " + toolName);
        }
        return tool.execute(request);
    }
}
