package com.ecommerce.model;

/**
 * Represents a single line item in the cart.
 * Stores only the productId + quantity; product details are
 * resolved by joining with the ProductRepository at service level.
 */
public class CartItem {

    private Long id;
    private Long productId;
    private int quantity;

    public CartItem() {
    }

    public CartItem(Long id, Long productId, int quantity) {
        this.id = id;
        this.productId = productId;
        this.quantity = quantity;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
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