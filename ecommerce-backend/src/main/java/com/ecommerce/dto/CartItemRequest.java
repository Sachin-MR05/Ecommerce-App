package com.ecommerce.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

/**
 * Body for POST /cart - add a product to the cart.
 */
public class CartItemRequest {

    @NotNull(message = "productId is required")
    private Long productId;

    @Min(value = 1, message = "quantity must be at least 1")
    private int quantity = 1;

    public CartItemRequest() {
    }

    public Long getProductId() {
        return productId;
    }

    public void setProductId(Long productId) {
        this.productId = productId;
    }

    public int getQuantity() {
        return quantity;
    }

    public void setQuantity(int quantity) {
        this.quantity = quantity;
    }
}