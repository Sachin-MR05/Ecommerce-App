package com.ecommerce.exception;

/**
 * Thrown when a requested Product or CartItem id doesn't exist.
 * Caught by GlobalExceptionHandler and turned into a 404.
 */
public class ResourceNotFoundException extends RuntimeException {

    public ResourceNotFoundException(String message) {
        super(message);
    }
}