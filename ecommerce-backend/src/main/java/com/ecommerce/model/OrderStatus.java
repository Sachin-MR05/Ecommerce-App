package com.ecommerce.model;

public enum OrderStatus {
    CREATED,   // razorpay order created, waiting for payment
    PAID,      // payment verified successfully
    FAILED     // payment verification failed
}
