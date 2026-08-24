package com.ecommerce.tools.product;

import com.ecommerce.adapter.merchant.MerchantCommerceAdapter;
import com.ecommerce.dto.ProductResponse;
import com.ecommerce.tools.AbstractAgentTool;
import com.ecommerce.tools.model.ToolRequest;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Searches the merchant's product catalog. Delegates entirely to
 * MerchantCommerceAdapter.searchProducts(), which itself reuses the
 * existing ProductService - no catalog/search logic lives here.
 */
@Component
public class SearchProductsTool extends AbstractAgentTool {

    private final MerchantCommerceAdapter merchantCommerceAdapter;

    public SearchProductsTool(MerchantCommerceAdapter merchantCommerceAdapter) {
        this.merchantCommerceAdapter = merchantCommerceAdapter;
    }

    @Override
    public String getName() {
        return "search_products";
    }

    @Override
    public String getDescription() {
        return "Search the merchant's product catalog by keyword. Matches against product name and " +
                "category. Omit the keyword (or leave it blank) to return the entire catalog. Use this " +
                "to find candidate products before calling get_product/check_inventory/get_price on a " +
                "specific one.";
    }

    @Override
    public String getInputSchema() {
        return """
                {
                  "type": "object",
                  "properties": {
                    "keyword": {
                      "type": "string",
                      "description": "Search term to match against product name or category. Optional."
                    }
                  },
                  "required": []
                }
                """;
    }

    @Override
    public String getOutputSchema() {
        return """
                {
                  "type": "array",
                  "items": {
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
                }
                """;
    }

    @Override
    protected Object handle(ToolRequest request) {
        String keyword = request.getOptionalString("keyword");
        List<ProductResponse> products = merchantCommerceAdapter.searchProducts(keyword, null);
        return products;
    }
}
