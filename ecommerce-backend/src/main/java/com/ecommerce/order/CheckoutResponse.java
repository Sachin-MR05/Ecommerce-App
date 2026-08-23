package com.ecommerce.order;

/**
 * Returned from POST /orders/checkout - everything the frontend needs
 * to open the Razorpay Checkout widget.
 */
public class CheckoutResponse {

    private Long orderId;            // our local order id
    private String razorpayOrderId;  // order id created on Razorpay's side
    private long amount;             // amount in paise (smallest currency unit)
    private String currency;
    private String keyId;            // Razorpay public key id, safe to expose to frontend

    public CheckoutResponse(Long orderId, String razorpayOrderId, long amount, String currency, String keyId) {
        this.orderId = orderId;
        this.razorpayOrderId = razorpayOrderId;
        this.amount = amount;
        this.currency = currency;
        this.keyId = keyId;
    }

    public Long getOrderId() {
        return orderId;
    }

    public String getRazorpayOrderId() {
        return razorpayOrderId;
    }

    public long getAmount() {
        return amount;
    }

    public String getCurrency() {
        return currency;
    }

    public String getKeyId() {
        return keyId;
    }
}
