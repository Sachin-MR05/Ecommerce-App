package com.ecommerce.tools.cart;

import com.ecommerce.adapter.merchant.MerchantCommerceAdapter;
import com.ecommerce.dto.CartResponse;
import com.ecommerce.tools.AbstractAgentTool;
import com.ecommerce.tools.model.ToolRequest;
import org.springframework.stereotype.Component;

/**
 * Removes a line item from the authenticated user's cart entirely.
 * Delegates to MerchantCommerceAdapter.removeFromCart(), which reuses the
 * existing CartService (including its ownership check).
 */
@Component
public class RemoveFromCartTool extends AbstractAgentTool {

    private final MerchantCommerceAdapter merchantCommerceAdapter;

    public RemoveFromCartTool(MerchantCommerceAdapter merchantCommerceAdapter) {
        this.merchantCommerceAdapter = merchantCommerceAdapter;
    }

    @Override
    public String getName() {
        return "remove_from_cart";
    }

    @Override
    public String getDescription() {
        return "Remove a single line item from the current user's cart entirely. Returns NOT_FOUND if " +
                "the cart item doesn't exist or doesn't belong to the current user.";
    }

    @Override
    public String getInputSchema() {
        return """
                {
                  "type": "object",
                  "properties": {
                    "cartItemId": { "type": "integer", "description": "Id of the cart line item to remove." }
                  },
                  "required": ["cartItemId"]
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

        CartResponse cart = merchantCommerceAdapter.removeFromCart(userId, cartItemId);
        return cart;
    }
}
