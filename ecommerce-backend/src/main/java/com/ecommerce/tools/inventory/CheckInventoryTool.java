package com.ecommerce.tools.inventory;

import com.ecommerce.adapter.merchant.MerchantCommerceAdapter;
import com.ecommerce.adapter.merchant.dto.InventoryCheckResult;
import com.ecommerce.tools.AbstractAgentTool;
import com.ecommerce.tools.model.ToolRequest;
import com.ecommerce.tools.model.ToolValidationException;
import org.springframework.stereotype.Component;

/**
 * Checks whether a requested quantity of a product is currently available.
 * Delegates to MerchantCommerceAdapter.checkInventory(), which reuses the
 * existing Product stock data - no separate stock/reservation logic here.
 *
 * Always call this (and get_price) again right before create_order - stock
 * and price can change between search and checkout.
 */
@Component
public class CheckInventoryTool extends AbstractAgentTool {

    private final MerchantCommerceAdapter merchantCommerceAdapter;

    public CheckInventoryTool(MerchantCommerceAdapter merchantCommerceAdapter) {
        this.merchantCommerceAdapter = merchantCommerceAdapter;
    }

    @Override
    public String getName() {
        return "check_inventory";
    }

    @Override
    public String getDescription() {
        return "Check whether a given quantity of a product is currently available in stock. Returns " +
                "a structured availability result - it never blocks the call itself, so the caller can " +
                "decide how to proceed (e.g. offer a smaller quantity) when stock is insufficient.";
    }

    @Override
    public String getInputSchema() {
        return """
                {
                  "type": "object",
                  "properties": {
                    "productId": { "type": "integer", "description": "Id of the product to check." },
                    "quantity": { "type": "integer", "description": "Quantity being requested. Must be at least 1." }
                  },
                  "required": ["productId", "quantity"]
                }
                """;
    }

    @Override
    public String getOutputSchema() {
        return """
                {
                  "type": "object",
                  "properties": {
                    "productId": { "type": "integer" },
                    "requestedQuantity": { "type": "integer" },
                    "availableQuantity": { "type": "integer" },
                    "available": { "type": "boolean" }
                  }
                }
                """;
    }

    @Override
    protected Object handle(ToolRequest request) {
        Long productId = request.getRequiredLong("productId");
        int quantity = request.getRequiredInt("quantity");
        if (quantity < 1) {
            throw new ToolValidationException("Parameter 'quantity' must be at least 1");
        }

        InventoryCheckResult result = merchantCommerceAdapter.checkInventory(productId, quantity);
        return result;
    }
}
