package com.ecommerce.exception;

/**
 * Thrown for checkout/payment problems (empty cart, Razorpay API errors,
 * signature verification failure). Caught by GlobalExceptionHandler.
 */
public class PaymentException extends RuntimeException {

    public PaymentException(String message) {
        super(message);
    }

    public PaymentException(String message, Throwable cause) {
        super(message, cause);
    }
}
