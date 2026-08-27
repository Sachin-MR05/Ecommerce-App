package com.ecommerce.tools.cart;

import com.ecommerce.adapter.merchant.MerchantCommerceAdapter;
import com.ecommerce.dto.CartResponse;
import com.ecommerce.tools.AbstractAgentTool;
import com.ecommerce.tools.model.ToolRequest;
import com.ecommerce.tools.model.ToolValidationException;
import org.springframework.stereotype.Component;

/**
 * Adds a product/quantity to the authenticated user's cart. Delegates to
 * MerchantCommerceAdapter.addToCart(), which reuses the existing
 * CartService (stock checking, existing-line-item merging, etc.).
 */
@Component
public class AddToCartTool extends AbstractAgentTool {

    private final MerchantCommerceAdapter merchantCommerceAdapter;

    public AddToCartTool(MerchantCommerceAdapter merchantCommerceAdapter) {
        this.merchantCommerceAdapter = merchantCommerceAdapter;
    }

    @Override
    public String getName() {
        return "add_to_cart";
    }

    @Override
    public String getDescription() {
        return "Add a quantity of a product to the current user's cart. If the product is already in " +
                "the cart, the quantity is increased. Returns INSUFFICIENT_STOCK if the resulting " +
                "quantity exceeds available stock.";
    }

    @Override
    public String getInputSchema() {
        return """
                {
                  "type": "object",
                  "properties": {
                    "productId": { "type": "integer", "description": "Id of the product to add." },
                    "quantity": { "type": "integer", "description": "Quantity to add. Must be at least 1." }
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
        Long productId = request.getRequiredLong("productId");
        int quantity = request.getRequiredInt("quantity");
        if (quantity < 1) {
            throw new ToolValidationException("Parameter 'quantity' must be at least 1");
        }

        CartResponse cart = merchantCommerceAdapter.addToCart(userId, productId, quantity);
        return cart;
    }
}
