package com.ecommerce.tools.order;

import com.ecommerce.adapter.merchant.MerchantCommerceAdapter;
import com.ecommerce.order.CheckoutResponse;
import com.ecommerce.tools.AbstractAgentTool;
import com.ecommerce.tools.model.ToolRequest;
import org.springframework.stereotype.Component;

/**
 * Turns the current user's cart into an order and starts the payment flow.
 * Delegates to MerchantCommerceAdapter.createCheckout(), which reuses the
 * existing OrderService (stock revalidation, live pricing, Razorpay order
 * creation) - no checkout/payment logic lives in this tool.
 *
 * The AI Agent should have already confirmed availability/price via
 * check_inventory/get_price - this call re-validates both server-side
 * regardless.
 */
@Component
public class CreateOrderTool extends AbstractAgentTool {

    private final MerchantCommerceAdapter merchantCommerceAdapter;

    public CreateOrderTool(MerchantCommerceAdapter merchantCommerceAdapter) {
        this.merchantCommerceAdapter = merchantCommerceAdapter;
    }

    @Override
    public String getName() {
        return "create_order";
    }

    @Override
    public String getDescription() {
        return "Create an order/checkout from the current user's cart and initialize the payment flow. " +
                "Validates stock and uses the live price for every cart line server-side. Returns " +
                "PAYMENT_ERROR if the cart is empty or a line item no longer has sufficient stock. The " +
                "resulting order is not marked paid until verify_payment succeeds.";
    }

    @Override
    public String getInputSchema() {
        return """
                {
                  "type": "object",
                  "properties": {},
                  "required": []
                }
                """;
    }

    @Override
    public String getOutputSchema() {
        return """
                {
                  "type": "object",
                  "properties": {
                    "orderId": { "type": "integer" },
                    "razorpayOrderId": { "type": "string" },
                    "amount": { "type": "integer", "description": "Amount in the smallest currency unit (e.g. paise)." },
                    "currency": { "type": "string" },
                    "keyId": { "type": "string" }
                  }
                }
                """;
    }

    @Override
    protected Object handle(ToolRequest request) {
        Long userId = requireUserId(request);
        CheckoutResponse checkoutResponse = merchantCommerceAdapter.createCheckout(userId);
        return checkoutResponse;
    }
}
