package com.ecommerce.tools.cart;

import com.ecommerce.adapter.merchant.MerchantCommerceAdapter;
import com.ecommerce.dto.CartResponse;
import com.ecommerce.tools.AbstractAgentTool;
import com.ecommerce.tools.model.ToolRequest;
import com.ecommerce.tools.model.ToolValidationException;
import org.springframework.stereotype.Component;

/**
 * Sets an existing cart item to an exact quantity. Delegates to
 * MerchantCommerceAdapter.updateCart(), which reuses the existing
 * CartService's stock-checked increase/decrease operations - no cart
 * mutation logic lives in this tool.
 */
@Component
public class UpdateCartTool extends AbstractAgentTool {

    private final MerchantCommerceAdapter merchantCommerceAdapter;

    public UpdateCartTool(MerchantCommerceAdapter merchantCommerceAdapter) {
        this.merchantCommerceAdapter = merchantCommerceAdapter;
    }

    @Override
    public String getName() {
        return "update_cart";
    }

    @Override
    public String getDescription() {
        return "Set an existing cart item to an exact quantity (not a delta). A quantity of 0 removes " +
                "the item. Returns INSUFFICIENT_STOCK if the requested quantity exceeds available stock, " +
                "or NOT_FOUND if the cart item doesn't belong to the current user.";
    }

    @Override
    public String getInputSchema() {
        return """
                {
                  "type": "object",
                  "properties": {
                    "cartItemId": { "type": "integer", "description": "Id of the cart line item to update." },
                    "quantity": { "type": "integer", "description": "New quantity for this line item. 0 removes it." }
                  },
                  "required": ["cartItemId", "quantity"]
                }
                """;
    }

    @Override
    public String getOutputSchema() {
        return """
                {
                  "type": "object",
                  "properties": {
                    "items": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "cartItemId": { "type": "integer" },
                          "productId": { "type": "integer" },
                          "productName": { "type": "string" },
                          "price": { "type": "number" },
                          "quantity": { "type": "integer" },
                          "subtotal": { "type": "number" }
                        }
                      }
                    },
                    "total": { "type": "number" },
                    "totalItems": { "type": "integer" }
                  }
                }
                """;
    }

    @Override
    protected Object handle(ToolRequest request) {
        Long userId = requireUserId(request);
        Long cartItemId = request.getRequiredLong("cartItemId");
        int quantity = request.getRequiredInt("quantity");
        if (quantity < 0) {
            throw new ToolValidationException("Parameter 'quantity' cannot be negative");
        }

        CartResponse cart = merchantCommerceAdapter.updateCart(userId, cartItemId, quantity);
        return cart;
    }
}
