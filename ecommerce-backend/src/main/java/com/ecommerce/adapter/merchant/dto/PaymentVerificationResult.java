package com.ecommerce.adapter.merchant.dto;

import com.ecommerce.order.OrderResponse;

/**
 * Structured result for MerchantCommerceAdapter.verifyPayment().
 *
 * The existing OrderService.verifyPayment() throws ResourceNotFoundException /
 * PaymentException, which is fine for the HTTP layer (GlobalExceptionHandler
 * turns those into clean 4xx responses). The AI Agent/Orchestrator calls the
 * adapter in-process though, so those exceptions never reach a controller -
 * the adapter catches them and reports a structured, unambiguous outcome
 * instead. An order is only ever attached when verified is true, i.e. only
 * after the existing server-side signature verification succeeded.
 */
public class PaymentVerificationResult {

    private boolean verified;
    private String message;
    private OrderResponse order;

    public PaymentVerificationResult() {
    }

    private PaymentVerificationResult(boolean verified, String message, OrderResponse order) {
        this.verified = verified;
        this.message = message;
        this.order = order;
    }

    public static PaymentVerificationResult verified(OrderResponse order) {
        return new PaymentVerificationResult(true, "Payment verified successfully", order);
    }

    public static PaymentVerificationResult failed(String message) {
        return new PaymentVerificationResult(false, message, null);
    }

    public boolean isVerified() {
        return verified;
    }

    public void setVerified(boolean verified) {
        this.verified = verified;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public OrderResponse getOrder() {
        return order;
    }

    public void setOrder(OrderResponse order) {
        this.order = order;
    }
}
