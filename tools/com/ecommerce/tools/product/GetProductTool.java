package com.ecommerce.tools.product;

import com.ecommerce.adapter.merchant.MerchantCommerceAdapter;
import com.ecommerce.dto.ProductResponse;
import com.ecommerce.tools.AbstractAgentTool;
import com.ecommerce.tools.model.ToolRequest;
import org.springframework.stereotype.Component;

/**
 * Retrieves complete information for a single product by id. Delegates to
 * MerchantCommerceAdapter.getProduct(), which reuses the existing
 * ProductService and its ResourceNotFoundException handling.
 */
@Component
public class GetProductTool extends AbstractAgentTool {

    private final MerchantCommerceAdapter merchantCommerceAdapter;

    public GetProductTool(MerchantCommerceAdapter merchantCommerceAdapter) {
        this.merchantCommerceAdapter = merchantCommerceAdapter;
    }

    @Override
    public String getName() {
        return "get_product";
    }

    @Override
    public String getDescription() {
        return "Retrieve complete details for a single product by its id: name, description, price, " +
                "category, stock, and image URL. Returns a NOT_FOUND error if the product doesn't exist.";
    }

    @Override
    public String getInputSchema() {
        return """
                {
                  "type": "object",
                  "properties": {
                    "productId": { "type": "integer", "description": "Id of the product to retrieve." }
                  },
                  "required": ["productId"]
                }
                """;
    }

    @Override
    public String getOutputSchema() {
        return """
                {
                  "type": "object",
                  "properties": {
                    "id": { "type": "integer" },
                    "name": { "type": "string" },
                    "description": { "type": "string" },
                    "price": { "type": "number" },
                    "category": { "type": "string" },
                    "stock": { "type": "integer" },
                    "imageUrl": { "type": "string" }
                  }
                }
                """;
    }

    @Override
    protected Object handle(ToolRequest request) {
        Long productId = request.getRequiredLong("productId");
        ProductResponse product = merchantCommerceAdapter.getProduct(productId, null);
        return product;
    }
}
