package com.ecommerce.tools.order;

import com.ecommerce.adapter.merchant.MerchantCommerceAdapter;
import com.ecommerce.order.OrderResponse;
import com.ecommerce.tools.AbstractAgentTool;
import com.ecommerce.tools.model.ToolRequest;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Retrieves the current user's order(s) - a single order by id, or the
 * full order history when no id is given. Delegates to
 * MerchantCommerceAdapter.getOrder()/getOrders(), which both reuse the
 * existing OrderService (including its user-ownership scoping).
 *
 * NOTE: getOrders(userId, baseUrl) - the list variant - is a one-line
 * pass-through to the already-existing OrderService.getOrders(userId, baseUrl)
 * (used today by GET /orders). It was not part of MerchantCommerceAdapter's
 * original 10 operations, so add this to MerchantCommerceAdapter /
 * MerchantCommerceAdapterImpl before wiring this tool in:
 *
 *   // MerchantCommerceAdapter
 *   List<OrderResponse> getOrders(Long userId, String baseUrl);
 *
 *   // MerchantCommerceAdapterImpl
 *   @Override
 *   public List<OrderResponse> getOrders(Long userId, String baseUrl) {
 *       return orderService.getOrders(userId, resolveBaseUrl(baseUrl));
 *   }
 */
@Component
public class GetOrdersTool extends AbstractAgentTool {

    private final MerchantCommerceAdapter merchantCommerceAdapter;

    public GetOrdersTool(MerchantCommerceAdapter merchantCommerceAdapter) {
        this.merchantCommerceAdapter = merchantCommerceAdapter;
    }

    @Override
    public String getName() {
        return "get_orders";
    }

    @Override
    public String getDescription() {
        return "Retrieve the current user's orders, including status - suitable for order/delivery " +
                "tracking. Pass orderId to retrieve a single order; omit it to retrieve the full order " +
                "history. Returns NOT_FOUND if orderId is given but doesn't belong to the current user.";
    }

    @Override
    public String getInputSchema() {
        return """
                {
                  "type": "object",
                  "properties": {
                    "orderId": {
                      "type": "integer",
                      "description": "Id of a single order to retrieve. Optional - omit for full order history."
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
                  "description": "A single order object when orderId was supplied, otherwise an array of order objects.",
                  "type": ["object", "array"],
                  "items": {
                    "type": "object",
                    "properties": {
                      "id": { "type": "integer" },
                      "status": { "type": "string", "enum": ["CREATED", "PAID", "FAILED"] },
                      "totalAmount": { "type": "number" },
                      "createdAt": { "type": "string" },
                      "razorpayOrderId": { "type": "string" },
                      "razorpayPaymentId": { "type": "string" },
                      "items": {
                        "type": "array",
                        "items": {
                          "type": "object",
                          "properties": {
                            "productId": { "type": "integer" },
                            "productName": { "type": "string" },
                            "imageUrl": { "type": "string" },
                            "price": { "type": "number" },
                            "quantity": { "type": "integer" }
                          }
                        }
                      }
                    }
                  }
                }
                """;
    }

    @Override
    protected Object handle(ToolRequest request) {
        Long userId = requireUserId(request);
        Long orderId = request.getOptionalLong("orderId");

        if (orderId != null) {
            OrderResponse order = merchantCommerceAdapter.getOrder(userId, orderId, null);
            return order;
        }

        List<OrderResponse> orders = merchantCommerceAdapter.getOrders(userId, null);
        return orders;
    }
}
