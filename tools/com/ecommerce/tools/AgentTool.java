package com.ecommerce.tools;

import com.ecommerce.tools.model.ToolRequest;
import com.ecommerce.tools.model.ToolResponse;

/**
 * Common contract for every agent-facing tool in this layer.
 *
 * This interface has no dependency on any specific LLM/agent framework
 * (no OpenAI/Gemini/Claude types anywhere in this package) - name,
 * description, and the two schemas are plain strings, so a thin adapter
 * at the very edge of the agent layer can translate them into whatever
 * function-calling format a given provider expects. Swapping providers
 * never requires touching a tool implementation.
 */
public interface AgentTool {

    /**
     * Stable, machine-readable tool identifier (e.g. "search_products").
     * This is what AgentToolRegistry indexes by and what the agent
     * references when invoking the tool.
     */
    String getName();

    /**
     * Human/LLM-readable description of what the tool does and when to use it.
     */
    String getDescription();

    /**
     * JSON-schema-shaped description (as a string) of the parameters this
     * tool accepts. Provider-agnostic - convert to OpenAI/Gemini/Claude's
     * native tool-schema format at the edge, not here.
     */
    String getInputSchema();

    /**
     * JSON-schema-shaped description (as a string) of the tool's successful
     * output shape, so the agent knows what fields to expect back.
     */
    String getOutputSchema();

    /**
     * Validates the request, delegates to MerchantCommerceAdapter, and
     * always returns a structured ToolResponse - it never throws.
     */
    ToolResponse execute(ToolRequest request);
}
