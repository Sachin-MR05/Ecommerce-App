package com.ecommerce.tools.pricing;

import com.ecommerce.adapter.merchant.MerchantCommerceAdapter;
import com.ecommerce.adapter.merchant.dto.PriceInfo;
import com.ecommerce.tools.AbstractAgentTool;
import com.ecommerce.tools.model.ToolRequest;
import org.springframework.stereotype.Component;

/**
 * Returns the current, live price for a product. Delegates to
 * MerchantCommerceAdapter.getPrice(), which always re-reads the product
 * record rather than relying on a value captured earlier during a search -
 * this tool never caches or recomputes pricing itself.
 */
@Component
public class GetPriceTool extends AbstractAgentTool {

    private final MerchantCommerceAdapter merchantCommerceAdapter;

    public GetPriceTool(MerchantCommerceAdapter merchantCommerceAdapter) {
        this.merchantCommerceAdapter = merchantCommerceAdapter;
    }

    @Override
    public String getName() {
        return "get_price";
    }

    @Override
    public String getDescription() {
        return "Get the current, live price of a product. Always reflects the merchant's latest price - " +
                "never rely on a price seen earlier in search_products; call this again right before " +
                "checkout.";
    }

    @Override
    public String getInputSchema() {
        return """
                {
                  "type": "object",
                  "properties": {
                    "productId": { "type": "integer", "description": "Id of the product to price." }
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
                    "productId": { "type": "integer" },
                    "price": { "type": "number" },
                    "currency": { "type": "string" }
                  }
                }
                """;
    }

    @Override
    protected Object handle(ToolRequest request) {
        Long productId = request.getRequiredLong("productId");
        PriceInfo priceInfo = merchantCommerceAdapter.getPrice(productId);
        return priceInfo;
    }
}
