package com.ecommerce.exception;

/**
 * Thrown when trying to add/increase a cart item beyond available stock.
 */
public class InsufficientStockException extends RuntimeException {

    public InsufficientStockException(String message) {
        super(message);
    }
}