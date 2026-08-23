package com.ecommerce.exception;

/**
 * Thrown for registration/login problems (duplicate email, bad credentials,
 * wrong admin invite code). Caught by GlobalExceptionHandler and turned into a 400/401.
 */
public class AuthException extends RuntimeException {

    public AuthException(String message) {
        super(message);
    }
}
