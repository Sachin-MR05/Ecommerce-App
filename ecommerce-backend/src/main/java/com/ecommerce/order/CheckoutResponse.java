package com.ecommerce.order;

public class CheckoutResponse {

    private Long orderId;
    private String razorpayOrderId;
    private long amount;
    private String currency;
    private String keyId;
    private String paymentLink;

    public CheckoutResponse(Long orderId, String razorpayOrderId, long amount,
                            String currency, String keyId, String paymentLink) {
        this.orderId = orderId;
        this.razorpayOrderId = razorpayOrderId;
        this.amount = amount;
        this.currency = currency;
        this.keyId = keyId;
        this.paymentLink = paymentLink;
    }

    public Long getOrderId() { return orderId; }
    public String getRazorpayOrderId() { return razorpayOrderId; }
    public long getAmount() { return amount; }
    public String getCurrency() { return currency; }
    public String getKeyId() { return keyId; }
    public String getPaymentLink() { return paymentLink; }
}
